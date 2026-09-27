from app.posts import format_panic_post, format_stage_post


def test_stage_escalation_message():
    msg = format_stage_post({"from_stage": 2, "to_stage": 4})
    assert "escalated to Stage 4" in msg


def test_stage_reduction_message():
    msg = format_stage_post({"from_stage": 4, "to_stage": 2})
    assert "reduced to Stage 2" in msg


def test_stage_zero_message():
    msg = format_stage_post({"from_stage": 2, "to_stage": 0})
    assert "suspended" in msg.lower()


def test_panic_message_includes_service_and_count():
    msg = format_panic_post({"service": "schedule-service", "count": 3, "window_seconds": 60})
    assert "schedule-service" in msg
    assert "3 failures" in msg
