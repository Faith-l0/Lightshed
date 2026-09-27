"""Schedule service.

Given a town and province, returns a loadshedding schedule as JSON.

Fault tolerance for its two upstream dependencies (Place-name, Stage):
  * Each call is retried with exponential backoff before being treated as a
    failure — a single dropped packet or a brief restart shouldn't surface
    as an error to our caller.
  * If Place-name still fails after retries, we return 503 (we can't answer
    without knowing whether the place is valid) AND publish a `service.failed`
    event so Monitor can notice a pattern of failures.
  * If Stage still fails after retries, we degrade gracefully: fall back to
    stage 0 and still return a schedule, but still publish `service.failed`
    so Monitor knows Stage is having trouble even though we papered over it
    for this particular request.
"""
import logging
import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .mq import publish_event
from .retry import retry_with_backoff
from .schedules import schedule_for

log = logging.getLogger("schedule-service")
logging.basicConfig(level=logging.INFO)

PLACE_SERVICE_URL = os.getenv("PLACE_SERVICE_URL", "http://localhost:8001")
STAGE_SERVICE_URL = os.getenv("STAGE_SERVICE_URL", "http://localhost:8002")
REQUEST_TIMEOUT = float(os.getenv("UPSTREAM_TIMEOUT", "3.0"))
RETRY_ATTEMPTS = int(os.getenv("UPSTREAM_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("UPSTREAM_RETRY_DELAY", "0.2"))

app = FastAPI(title="LightShed Schedule Service")


@app.get("/health")
def health():
    return {"status": "ok"}


async def _get_with_retry(url: str, params: dict) -> httpx.Response:
    async def attempt():
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            return await client.get(url, params=params)

    return await retry_with_backoff(
        attempt,
        retries=RETRY_ATTEMPTS,
        base_delay=RETRY_BASE_DELAY,
        retry_on=(httpx.RequestError,),
    )


async def _validate_place(town: str, province: str | None) -> tuple[dict | None, JSONResponse | None]:
    """Returns (validated_place, None) on success, or (None, error_response) on failure."""
    params = {"town": town}
    if province:
        params["province"] = province
    try:
        resp = await _get_with_retry(f"{PLACE_SERVICE_URL}/places/validate", params)
    except httpx.RequestError as exc:
        log.error("Place-name service unreachable after retries: %s", exc)
        await publish_event("service.failed", {"service": "place-service", "detail": str(exc)})
        return None, JSONResponse(
            {"status": "upstream_unavailable", "service": "place-name", "detail": str(exc)},
            status_code=503,
        )

    body = resp.json()
    if resp.status_code != 200:
        # Place-name reached us fine and told us the place is invalid somehow;
        # forward its status code and body rather than reinterpreting it. This
        # is not a "failure" of the service, so no service.failed event.
        return None, JSONResponse(body, status_code=resp.status_code)
    return body, None


async def _current_stage() -> int:
    """Best-effort fetch of the current stage. Falls back to stage 0 (unknown-safe)
    if the Stage service can't be reached, rather than failing the whole request —
    but still tells Monitor about the failure so it isn't silently masked."""
    try:
        resp = await _get_with_retry(f"{STAGE_SERVICE_URL}/stage", {})
        resp.raise_for_status()
        return resp.json()["stage"]
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        log.warning("Stage service unreachable after retries, defaulting to stage 0: %s", exc)
        await publish_event("service.failed", {"service": "stage-service", "detail": str(exc)})
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
