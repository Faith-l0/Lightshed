from fastapi.testclient import TestClient

from app.main import app, state

client = TestClient(app)


def setup_function():
    state.stage = 0
    state.history = []


def test_default_stage_is_zero():
    r = client.get("/stage")
    assert r.status_code == 200
    assert r.json()["stage"] == 0


def test_set_stage_updates_value():
    r = client.put("/stage", json={"stage": 4})
    assert r.status_code == 200
    assert client.get("/stage").json()["stage"] == 4


def test_out_of_range_stage_rejected():
    r = client.put("/stage", json={"stage": 9})
    assert r.status_code == 422
    r = client.put("/stage", json={"stage": -1})
    assert r.status_code == 422


def test_history_records_changes():
    client.put("/stage", json={"stage": 2})
    client.put("/stage", json={"stage": 6})
    history = client.get("/stage/history").json()
    assert [h["to_stage"] for h in history] == [2, 6]
