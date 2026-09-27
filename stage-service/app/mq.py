"""RabbitMQ helper: publish events to the 'lightshed' topic exchange.

Design choices worth explaining in the write-up:
  * Publishing is fire-and-forget from the caller's point of view: if RabbitMQ
    is unreachable, we log and swallow the error rather than raising, so a
    broker outage never turns into a 500 for the person calling our HTTP API.
    Losing an event is a lesser problem than losing an entire user request.
  * The exchange is 'topic' so routing keys like "service.failed" or
    "stage.changed" can be pattern-matched (e.g. "#.failed") by consumers.
  * Messages are marked persistent (delivery_mode=2) so they survive a
    RabbitMQ restart if they're sitting in a durable queue.
"""
import json
import logging
import os

import aio_pika

log = logging.getLogger("mq")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = "lightshed"

_connection: aio_pika.RobustConnection | None = None


async def _get_channel() -> aio_pika.abc.AbstractChannel:
    global _connection
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(RABBITMQ_URL, timeout=3)
    return await _connection.channel()


async def publish_event(routing_key: str, payload: dict) -> bool:
    """Best-effort publish. Returns True if it went out, False if it didn't
    (broker down, timeout, etc.) — callers can log that but should NOT fail
    the request because of it."""
    try:
        channel = await _get_channel()
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        message = aio_pika.Message(
            body=json.dumps(payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await exchange.publish(message, routing_key=routing_key)
        return True
    except Exception as exc:  # noqa: BLE001 - broker being down is expected, not exceptional
        log.warning("Could not publish event %r: %s", routing_key, exc)
        return False
