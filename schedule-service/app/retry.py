"""A small, dependency-free retry helper with exponential backoff.

Kept separate from main.py so the backoff math can be unit tested without
spinning up HTTP mocks.
"""
import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def retry_with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    base_delay: float = 0.2,
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Call `fn()` (an async no-arg callable). On a matching exception, wait
    base_delay * 2**attempt seconds and try again, up to `retries` attempts
    total. Re-raises the last exception if every attempt fails."""
    attempt = 0
    while True:
        try:
            return await fn()
        except retry_on as exc:
            attempt += 1
            if attempt >= retries:
                raise
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
