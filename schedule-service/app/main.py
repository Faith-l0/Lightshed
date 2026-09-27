"""Schedule service.

Given a town and province, returns a loadshedding schedule as JSON.

Before returning a schedule it validates the place against the Place-name
service over HTTP — this is the inter-service communication this iteration
is meant to demonstrate. Two things can go wrong on that call, and each is
handled distinctly rather than collapsed into one generic error:

  * Place-name is reachable but says the place is invalid/ambiguous/unknown
    -> pass that outcome straight through to our caller.
  * Place-name is unreachable or times out
    -> return 503, so our caller can tell "the place doesn't exist" apart
       from "we couldn't check right now."
"""
import logging
import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .schedules import schedule_for

log = logging.getLogger("schedule-service")
logging.basicConfig(level=logging.INFO)

PLACE_SERVICE_URL = os.getenv("PLACE_SERVICE_URL", "http://localhost:8001")
STAGE_SERVICE_URL = os.getenv("STAGE_SERVICE_URL", "http://localhost:8002")
REQUEST_TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "3.0"))

app = FastAPI(title="LightShed Schedule Service")


@app.get("/health")
def health():
    return {"status": "ok"}


async def _validate_place(town: str, province: str | None) -> tuple[dict | None, JSONResponse | None]:
    """Returns (validated_place, None) on success, or (None, error_response) on failure."""
    params = {"town": town}
    if province:
        params["province"] = province
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(f"{PLACE_SERVICE_URL}/places/validate", params=params)
    except httpx.RequestError as exc:
        log.error("Place-name service unreachable: %s", exc)
        return None, JSONResponse(
            {"status": "upstream_unavailable", "service": "place-name", "detail": str(exc)},
            status_code=503,
        )

    body = resp.json()
    if resp.status_code != 200:
        # Place-name reached us fine and told us the place is invalid somehow;
        # forward its status code and body rather than reinterpreting it.
        return None, JSONResponse(body, status_code=resp.status_code)
    return body, None


async def _current_stage() -> int:
    """Best-effort fetch of the current stage. Falls back to stage 0 (unknown-safe)
    if the Stage service can't be reached, rather than failing the whole request."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(f"{STAGE_SERVICE_URL}/stage")
            resp.raise_for_status()
            return resp.json()["stage"]
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        log.warning("Stage service unreachable, defaulting to stage 0: %s", exc)
        return 0


@app.get("/schedule")
async def get_schedule(town: str, province: str | None = None):
    place, error = await _validate_place(town, province)
    if error is not None:
        return error

    stage = await _current_stage()
    entries = schedule_for(place["town"], place["province"], stage)
    return {
        "town": place["town"],
        "province": place["province"],
        "stage": stage,
        "schedule": entries,
    }
