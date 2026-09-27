"""Fake schedule data generation.

A real system would look these up from municipal schedule tables. Here we
generate a deterministic, plausible-looking schedule per (town, stage) so the
service has something real to return while the actual data source is unknown.
"""
import hashlib

SLOTS = ["02:00-04:30", "06:00-08:30", "10:00-12:30", "14:00-16:30", "18:00-20:30", "22:00-00:30"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def schedule_for(town: str, province: str, stage: int) -> list[dict]:
    if stage <= 0:
        return []
    # Deterministic pseudo-random offset per town, so results are stable across calls
    # but differ between towns instead of all returning the same slots.
    seed = int(hashlib.sha256(f"{town}|{province}".encode()).hexdigest(), 16)
    entries = []
    for i, day in enumerate(DAYS):
        slot_index = (seed + i * stage) % len(SLOTS)
        entries.append({"day": day, "slot": SLOTS[slot_index]})
    return entries
