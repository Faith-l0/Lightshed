"""Stage service.

Holds the current loadshedding stage in memory and exposes it to other services.
A real deployment would source this from Eskom's API or a control-room feed;
here it's a simple settable value so Schedule/AlertBot have something to react to.
"""
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("stage-service")
logging.basicConfig(level=logging.INFO)

MIN_STAGE = 0
MAX_STAGE = 8


class StageState:
    def __init__(self):
        self.stage = 0
        self.updated_at = datetime.now(timezone.utc)
        self.history: list[dict] = []

    def set_stage(self, new_stage: int) -> dict:
        old_stage = self.stage
        self.stage = new_stage
        self.updated_at = datetime.now(timezone.utc)
        event = {
            "from_stage": old_stage,
            "to_stage": new_stage,
            "at": self.updated_at.isoformat(),
        }
        self.history.append(event)
        if old_stage != new_stage:
            log.info("Stage changed: %d -> %d", old_stage, new_stage)
        return event


state = StageState()


class StageUpdate(BaseModel):
    stage: int = Field(ge=MIN_STAGE, le=MAX_STAGE)


app = FastAPI(title="LightShed Stage Service")


@app.get("/health")
def health():
    return {"status": "ok", "current_stage": state.stage}


@app.get("/stage")
def get_stage():
    return {"stage": state.stage, "updated_at": state.updated_at.isoformat()}


@app.put("/stage")
def set_stage(update: StageUpdate):
    if not (MIN_STAGE <= update.stage <= MAX_STAGE):
        # Belt-and-braces: pydantic already enforces this, but keep an explicit
        # domain check here since "valid stage" is a business rule, not just a type.
        raise HTTPException(422, f"stage must be between {MIN_STAGE} and {MAX_STAGE}")
    event = state.set_stage(update.stage)
    return event


@app.get("/stage/history")
def get_history():
    return state.history
