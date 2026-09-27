from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["places"] > 0


def test_valid_unambiguous_town_any_spelling():
    r = client.get("/places/validate", params={"town": "  CAPE town"})
    assert r.status_code == 200
    assert r.json() == {"status": "valid", "town": "Cape Town", "province": "Western Cape"}


def test_ambiguous_town_returns_409_with_provinces():
    r = client.get("/places/validate", params={"town": "Newlands"})
    assert r.status_code == 409
    assert r.json()["provinces"] == ["Gauteng", "KwaZulu-Natal", "Western Cape"]


def test_province_resolves_ambiguity():
    r = client.get("/places/validate", params={"town": "Newlands", "province": "KZN"})
    assert r.status_code == 200
    assert r.json()["province"] == "KwaZulu-Natal"


def test_typo_gets_suggestion():
    r = client.get("/places/validate", params={"town": "Stellenbosh"})
    assert r.status_code == 404
    assert "Stellenbosch" in r.json()["suggestions"]


def test_invalid_province():
    r = client.get("/places/validate", params={"town": "Paarl", "province": "Narnia"})
    assert r.status_code == 422


def test_town_in_wrong_province_is_not_found():
    r = client.get("/places/validate", params={"town": "Paarl", "province": "Gauteng"})
    assert r.status_code == 404
