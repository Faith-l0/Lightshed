"""Pure message-formatting logic, kept separate from the queue plumbing so
it's easy to unit test and easy to swap wording without touching main.py.
"""


def format_stage_post(event: dict) -> str:
    from_stage = event.get("from_stage")
    to_stage = event.get("to_stage")
    if to_stage == 0:
        return "Loadshedding has been suspended. Stage 0 in effect."
    if from_stage is not None and from_stage < to_stage:
        return f"Loadshedding has escalated to Stage {to_stage}."
    if from_stage is not None and from_stage > to_stage:
        return f"Loadshedding has been reduced to Stage {to_stage}."
    return f"Loadshedding is at Stage {to_stage}."


def format_panic_post(event: dict) -> str:
    service = event.get("service", "a service")
    count = event.get("count", "several")
    window = event.get("window_seconds", "a short period")
    return (
        f"We're experiencing technical issues with {service} "
        f"({count} failures in {window}s). We're on it — schedules may be delayed."
    )
