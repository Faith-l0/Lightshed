"""Pure decision logic for panic alerts, kept separate from the queue
plumbing in main.py so it's trivial to unit test without a broker.
"""
import time
from collections import defaultdict, deque

FAILURE_WINDOW_SECONDS = 60
FAILURE_THRESHOLD = 3


class FailureTracker:
    """Tracks recent failure timestamps per service and decides when a
    burst of failures crosses the line into 'raise a panic alert'."""

    def __init__(self, window_seconds: int = FAILURE_WINDOW_SECONDS, threshold: int = FAILURE_THRESHOLD):
        self.window_seconds = window_seconds
        self.threshold = threshold
        self._events: dict[str, deque] = defaultdict(deque)

    def record_failure(self, service: str, at: float | None = None) -> dict | None:
        """Record a failure for `service`. Returns a panic-alert payload if
        this failure pushed the service over the threshold within the
        window, otherwise None."""
        now = at if at is not None else time.time()
        q = self._events[service]
        q.append(now)
        cutoff = now - self.window_seconds
        while q and q[0] < cutoff:
            q.popleft()

        if len(q) >= self.threshold:
            alert = {
                "service": service,
                "count": len(q),
                "window_seconds": self.window_seconds,
                "at": now,
            }
            q.clear()  # don't immediately re-fire on the very next failure
            return alert
        return None
