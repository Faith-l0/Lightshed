"""AlertBot.

Consumes `stage.changed` events (from Stage service) and `panic.alert`
events (from Monitor), and publicly announces them. This is the "notify
users proactively via social media" piece of the brief.

No real social-media credentials are wired up here on purpose — that's an
account-specific integration you'd add per platform. Instead, `_post()` is
the single place a real API call would go; everywhere else in this file is
plumbing that stays the same regardless of which platform you post to.
Posts are also kept in memory and exposed at GET /posts so you can verify
the bot is reacting correctly without needing a live social account.
"""
import asyncio
import json
import logging
import os

import aio_pika
from fastapi import FastAPI

from .mq import EXCHANGE_NAME, RABBITMQ_URL
from .posts import format_panic_post, format_stage_post

log = logging.getLogger("alert-bot")
logging.basicConfig(level=logging.INFO)

DLX_NAME = "lightshed.dlx"
QUEUE_NAME = "alertbot.events"
MAX_HISTORY = 100

posts: list[dict] = []


def _post(text: str, kind: str):
    """Where a real integration lives. Swap this body for e.g. a Mastodon or
    X API call; keep the same signature so the rest of the bot is untouched."""
    if os.getenv("SOCIAL_DRY_RUN", "1") == "1":
        log.info("[DRY RUN] Would post (%s): %s", kind, text)
    else:
        # e.g. mastodon_client.post(text)
        raise NotImplementedError("Wire up a real social API client here")
    posts.append({"kind": kind, "text": text})
    del posts[:-MAX_HISTORY]


async def _handle_event(routing_key: str, event: dict):
    if routing_key == "stage.changed":
        if event.get("from_stage") == event.get("to_stage"):
            return  # nothing actually changed; don't spam a post
        _post(format_stage_post(event), kind="stage")
    elif routing_key == "panic.alert":
        _post(format_panic_post(event), kind="panic")
    else:
        log.info("Ignoring unrecognised routing key: %s", routing_key)


async def _consume_forever():
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
                queue = await channel.declare_queue(
                    QUEUE_NAME,
                    durable=True,
                    arguments={"x-dead-letter-exchange": DLX_NAME},
                )
                await queue.bind(exchange, routing_key="stage.changed")
                await queue.bind(exchange, routing_key="panic.alert")

                log.info("AlertBot connected, listening for stage.changed / panic.alert")
                delay = 1

                async with queue.iterator() as it:
                    async for message in it:
                        async with message.process(requeue=False):
                            await _handle_event(message.routing_key, json.loads(message.body))
        except Exception as exc:  # noqa: BLE001 - broker down/restarting is expected
            log.warning("AlertBot lost connection to RabbitMQ (%s), retrying in %ds", exc, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


app = FastAPI(title="LightShed AlertBot")
_consumer_task: asyncio.Task | None = None


@app.on_event("startup")
async def start_consumer():
    global _consumer_task
    if os.getenv("DISABLE_MQ_CONSUMER") != "1":
        _consumer_task = asyncio.create_task(_consume_forever())


@app.on_event("shutdown")
async def stop_consumer():
    if _consumer_task:
        _consumer_task.cancel()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/posts")
def get_posts():
    return posts
