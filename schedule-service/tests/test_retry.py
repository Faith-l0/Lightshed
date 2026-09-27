import pytest

from app.retry import retry_with_backoff


async def test_succeeds_first_try_no_delay():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = await retry_with_backoff(fn, retries=3, base_delay=0.01)
    assert result == "ok"
    assert len(calls) == 1


async def test_retries_then_succeeds():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("boom")
        return "ok"

    result = await retry_with_backoff(fn, retries=5, base_delay=0.001)
    assert result == "ok"
    assert len(calls) == 3


async def test_raises_after_exhausting_retries():
    async def fn():
        raise ConnectionError("boom")

    with pytest.raises(ConnectionError):
        await retry_with_backoff(fn, retries=2, base_delay=0.001)
