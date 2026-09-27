import os

os.environ["DISABLE_MQ_CONSUMER"] = "1"
os.environ["SOCIAL_DRY_RUN"] = "1"

from fastapi.testclient import TestClient

from app.main import _handle_event, app, posts

client = TestClient(app)


def setup_function():
    posts.clear()


def test_health():
    assert client.get("/health").status_code == 200


def test_posts_start_empty():
    assert client.get("/posts").json() == []


async def test_stage_change_creates_a_post():
    await _handle_event("stage.changed", {"from_stage": 1, "to_stage": 3})
    assert len(posts) == 1
    assert posts[0]["kind"] == "stage"


async def test_unchanged_stage_does_not_post():
    await _handle_event("stage.changed", {"from_stage": 3, "to_stage": 3})
    assert len(posts) == 0


async def test_panic_alert_creates_a_post():
    await _handle_event("panic.alert", {"service": "place-service", "count": 5, "window_seconds": 60})
    assert len(posts) == 1
    assert posts[0]["kind"] == "panic"
