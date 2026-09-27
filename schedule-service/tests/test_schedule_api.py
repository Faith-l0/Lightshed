from unittest.mock import AsyncMock, patch

import respx
import httpx
from fastapi.testclient import TestClient

from app.main import app, PLACE_SERVICE_URL, STAGE_SERVICE_URL

client = TestClient(app)


@respx.mock
@patch("app.main.publish_event", new_callable=AsyncMock)
def test_valid_town_returns_schedule(mock_publish):
    respx.get(f"{PLACE_SERVICE_URL}/places/validate").mock(
        return_value=httpx.Response(200, json={"status": "valid", "town": "Cape Town", "province": "Western Cape"})
    )
    respx.get(f"{STAGE_SERVICE_URL}/stage").mock(
        return_value=httpx.Response(200, json={"stage": 4, "updated_at": "now"})
    )
    r = client.get("/schedule", params={"town": "cape town"})
    assert r.status_code == 200
    body = r.json()
    assert body["town"] == "Cape Town"
    assert body["stage"] == 4
    assert len(body["schedule"]) == 7
    mock_publish.assert_not_awaited()  # nothing failed, nothing to report


@respx.mock
@patch("app.main.publish_event", new_callable=AsyncMock)
def test_stage_zero_means_no_schedule(mock_publish):
    respx.get(f"{PLACE_SERVICE_URL}/places/validate").mock(
        return_value=httpx.Response(200, json={"status": "valid", "town": "Durban", "province": "KwaZulu-Natal"})
    )
    respx.get(f"{STAGE_SERVICE_URL}/stage").mock(
        return_value=httpx.Response(200, json={"stage": 0, "updated_at": "now"})
    )
    r = client.get("/schedule", params={"town": "Durban"})
    assert r.json()["schedule"] == []


@respx.mock
@patch("app.main.publish_event", new_callable=AsyncMock)
def test_unknown_town_is_passed_through_as_404(mock_publish):
    respx.get(f"{PLACE_SERVICE_URL}/places/validate").mock(
        return_value=httpx.Response(404, json={"status": "not_found", "town": "Xyz", "suggestions": []})
    )
    r = client.get("/schedule", params={"town": "Xyz"})
    assert r.status_code == 404
    assert r.json()["status"] == "not_found"
    mock_publish.assert_not_awaited()  # a "not found" is not a service failure


@respx.mock
@patch("app.main.publish_event", new_callable=AsyncMock)
def test_ambiguous_town_is_passed_through_as_409(mock_publish):
    respx.get(f"{PLACE_SERVICE_URL}/places/validate").mock(
        return_value=httpx.Response(409, json={"status": "ambiguous", "town": "Newlands", "provinces": ["Gauteng", "Western Cape"]})
    )
    r = client.get("/schedule", params={"town": "Newlands"})
    assert r.status_code == 409


@respx.mock
@patch("app.main.publish_event", new_callable=AsyncMock)
def test_place_service_down_returns_503_and_reports_failure(mock_publish):
    respx.get(f"{PLACE_SERVICE_URL}/places/validate").mock(side_effect=httpx.ConnectError("connection refused"))
    r = client.get("/schedule", params={"town": "Cape Town"})
    assert r.status_code == 503
    assert r.json()["status"] == "upstream_unavailable"
    mock_publish.assert_awaited_once()
    args = mock_publish.call_args.args
    assert args[0] == "service.failed"
    assert args[1]["service"] == "place-service"


@respx.mock
@patch("app.main.publish_event", new_callable=AsyncMock)
def test_stage_service_down_falls_back_to_zero_and_reports_failure(mock_publish):
    respx.get(f"{PLACE_SERVICE_URL}/places/validate").mock(
        return_value=httpx.Response(200, json={"status": "valid", "town": "Cape Town", "province": "Western Cape"})
    )
    respx.get(f"{STAGE_SERVICE_URL}/stage").mock(side_effect=httpx.ConnectError("connection refused"))
    r = client.get("/schedule", params={"town": "Cape Town"})
    assert r.status_code == 200
    assert r.json()["stage"] == 0
    mock_publish.assert_awaited_once()
    assert mock_publish.call_args.args[1]["service"] == "stage-service"
