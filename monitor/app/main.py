"""Monitor service.

Consumes `service.failed` events published by other services, tracks how
often each service is failing, and raises a `panic.alert` event when a
service fails repeatedly within a short window. This is the proactive
monitoring piece of the system: nobody has to be watching logs for this
to be noticed.

The consumer runs as a background task started on FastAPI startup, using a
durable queue bound to the 'lightshed' topic exchange with a dead-letter
exchange configured, so a message that repeatedly fails processing doesn't
loop forever or vanish silently — it lands in `lightshed.dlq` for a human
to inspect later.
"""
import asyncio
import json
import logging
import os

import aio_pika
from fastapi import FastAPI

from .mq import EXCHANGE_NAME, RABBITMQ_URL, publish_event
from .panic import FailureTracker

log = logging.getLogger("monitor")
logging.basicConfig(level=logging.INFO)

DLX_NAME = "lightshed.dlx"
QUEUE_NAME = "monitor.failures"
DLQ_NAME = "lightshed.dlq"

tracker = FailureTracker()
recent_failures: list[dict] = []
recent_panics: list[dict] = []
MAX_HISTORY = 100


async def _consume_forever():
    """Connect to RabbitMQ and process `service.failed` events until cancelled.
    Retries the connection with backoff if the broker isn't up yet — this
    lets the monitor container start before/alongside RabbitMQ in compose."""
    delay = 1
    while True:
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=10)

                exchange = await channel.declare_exchange(
                    EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
                )
                dlx = await channel.declare_exchange(
                    DLX_NAME, aio_pika.ExchangeType.FANOUT, durable=True
                )
                dlq = await channel.declare_queue(DLQ_NAME, durable=True)
                await dlq.bind(dlx)

                queue = await channel.declare_queue(
                    QUEUE_NAME,
                    durable=True,
                    arguments={"x-dead-letter-exchange": DLX_NAME},
                )
                await queue.bind(exchange, routing_key="service.failed")

                log.info("Monitor connected, listening for service.failed events")
                delay = 1  # reset backoff after a successful connect

                async with queue.iterator() as it:
                    async for message in it:
                        async with message.process(requeue=False):
                            # requeue=False: if handling raises, the message goes
                            # to the DLQ above instead of looping forever.
                            await _handle_failure(json.loads(message.body))
        except Exception as exc:  # noqa: BLE001 - broker down/restarting is expected
            log.warning("Monitor lost connection to RabbitMQ (%s), retrying in %ds", exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


async def _handle_failure(event: dict):
    service = event.get("service", "unknown")
    log.warning("Recorded failure for %s: %s", service, event.get("detail"))
    recent_failures.append(event)
    del recent_failures[:-MAX_HISTORY]

    alert = tracker.record_failure(service)
    if alert:
        log.error("PANIC: %s failed %d times in %ds", service, alert["count"], alert["window_seconds"])
        recent_panics.append(alert)
        del recent_panics[:-MAX_HISTORY]
        await publish_event("panic.alert", alert)


app = FastAPI(title="LightShed Monitor")
_consumer_task: asyncio.Task | None = None


@app.on_event("startup")
async def start_consumer():
    global _consumer_task
    if os.getenv("DISABLE_MQ_CONSUMER") != "1":  # escape hatch for tests
        _consumer_task = asyncio.create_task(_consume_forever())


@app.on_event("shutdown")
async def stop_consumer():
    if _consumer_task:
        _consumer_task.cancel()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/failures")
def get_failures():
    return recent_failures


@app.get("/alerts")
def get_alerts():
    return recent_panics
