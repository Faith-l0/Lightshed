from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app, state

client = TestClient(app)


def setup_function():
    state.stage = 0
    state.history = []


@patch("app.main.publish_event", new_callable=AsyncMock)
def test_default_stage_is_zero(mock_publish):
    r = client.get("/stage")
    assert r.status_code == 200
    assert r.json()["stage"] == 0


@patch("app.main.publish_event", new_callable=AsyncMock)
def test_set_stage_updates_value(mock_publish):
    r = client.put("/stage", json={"stage": 4})
    assert r.status_code == 200
    assert client.get("/stage").json()["stage"] == 4


@patch("app.main.publish_event", new_callable=AsyncMock)
def test_out_of_range_stage_rejected(mock_publish):
    r = client.put("/stage", json={"stage": 9})
    assert r.status_code == 422
    r = client.put("/stage", json={"stage": -1})
    assert r.status_code == 422


@patch("app.main.publish_event", new_callable=AsyncMock)
def test_history_records_changes(mock_publish):
    client.put("/stage", json={"stage": 2})
    client.put("/stage", json={"stage": 6})
    history = client.get("/stage/history").json()
    assert [h["to_stage"] for h in history] == [2, 6]


@patch("app.main.publish_event", new_callable=AsyncMock)
def test_stage_change_publishes_event(mock_publish):
    client.put("/stage", json={"stage": 3})
    mock_publish.assert_awaited_once()
    args = mock_publish.call_args.args
    assert args[0] == "stage.changed"
    assert args[1]["from_stage"] == 0
    assert args[1]["to_stage"] == 3


@patch("app.main.publish_event", new_callable=AsyncMock)
def test_setting_same_stage_does_not_publish(mock_publish):
    client.put("/stage", json={"stage": 0})  # already 0, no change
    mock_publish.assert_not_awaited()
