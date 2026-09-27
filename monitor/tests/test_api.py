import os

os.environ["DISABLE_MQ_CONSUMER"] = "1"  # must be set before importing app.main

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").status_code == 200


def test_failures_and_alerts_start_empty():
    assert client.get("/failures").json() == []
    assert client.get("/alerts").json() == []
