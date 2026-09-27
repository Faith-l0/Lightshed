import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .cleaning import clean_file
from .store import PlaceStore

log = logging.getLogger("place-service")
logging.basicConfig(level=logging.INFO)

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "raw_places.csv"

# HTTP status per validation outcome. This is the contract other services
# (e.g. Schedule) will rely on, so keep it stable and document it.
STATUS_CODES = {
    "valid": 200,
    "not_found": 404,
    "ambiguous": 409,
    "invalid_province": 422,
}


def create_app(data_path: str | None = None) -> FastAPI:
    path = data_path or os.getenv("PLACES_DATA", str(DEFAULT_DATA))
    result = clean_file(path)
    store = PlaceStore(result.places)
    log.info(
        "Loaded %d places (%d duplicates dropped, %d rows rejected)",
        store.count, result.duplicates, len(result.rejected),
    )
    for r in result.rejected:
        log.warning("Rejected line %d (%r, %r): %s", r.line, r.town, r.province, r.reason)

    app = FastAPI(title="LightShed Place-name Service")

    @app.get("/health")
    def health():
        return {"status": "ok", "places": store.count}

    @app.get("/places/validate")
    def validate(town: str, province: str | None = None):
        outcome = store.validate(town, province)
        return JSONResponse(outcome, status_code=STATUS_CODES[outcome["status"]])

    @app.get("/places")
    def list_places(province: str | None = None):
        return [{"town": p.town, "province": p.province} for p in store.list_places(province)]

    return app


app = create_app()
