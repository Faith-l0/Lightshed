from app.panic import FailureTracker


def test_no_alert_below_threshold():
    t = FailureTracker(window_seconds=60, threshold=3)
    assert t.record_failure("schedule-service", at=0) is None
    assert t.record_failure("schedule-service", at=1) is None


def test_alert_fires_at_threshold():
    t = FailureTracker(window_seconds=60, threshold=3)
    assert t.record_failure("schedule-service", at=0) is None
    assert t.record_failure("schedule-service", at=1) is None
    alert = t.record_failure("schedule-service", at=2)
    assert alert == {"service": "schedule-service", "count": 3, "window_seconds": 60, "at": 2}


def test_failures_outside_window_dont_count():
    t = FailureTracker(window_seconds=10, threshold=3)
    t.record_failure("place-service", at=0)
    t.record_failure("place-service", at=1)
    # This third failure is 20s later -> first two have aged out of the window
    alert = t.record_failure("place-service", at=21)
    assert alert is None


def test_services_tracked_independently():
    t = FailureTracker(window_seconds=60, threshold=2)
    t.record_failure("schedule-service", at=0)
    alert = t.record_failure("place-service", at=0)
    assert alert is None  # place-service only has 1 failure so far


def test_tracker_resets_after_firing():
    t = FailureTracker(window_seconds=60, threshold=2)
    t.record_failure("schedule-service", at=0)
    first = t.record_failure("schedule-service", at=1)
    assert first is not None
    # immediately after firing, count restarts from zero
    second = t.record_failure("schedule-service", at=2)
    assert second is None
