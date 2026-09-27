"""Stage service.

Holds the current loadshedding stage in memory and exposes it to other
services. When the stage actually changes, it publishes a `stage.changed`
event to RabbitMQ so AlertBot (Iteration 4) can react without polling.
"""
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .mq import publish_event

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
async def set_stage(update: StageUpdate):
    if not (MIN_STAGE <= update.stage <= MAX_STAGE):
        raise HTTPException(422, f"stage must be between {MIN_STAGE} and {MAX_STAGE}")
    event = state.set_stage(update.stage)
    if event["from_stage"] != event["to_stage"]:
        # Best-effort: a broker outage must not stop the stage update itself
        # from succeeding, so this is awaited but its failure is non-fatal
        # (see mq.publish_event).
        await publish_event("stage.changed", event)
    return event


@app.get("/stage/history")
def get_history():
    return state.history
