import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry_with_jitter(
    func: Callable[[], Awaitable[T]],
    *,
    retryable: tuple[type[Exception], ...],
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    attempt = 0
    while True:
        try:
            return await func()
        except retryable:
            attempt += 1
            if attempt >= max_attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            await sleep(random.uniform(0, delay))