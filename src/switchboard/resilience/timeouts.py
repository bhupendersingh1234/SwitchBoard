import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class DeadlineExceeded(Exception):
    pass


async def with_deadline(func: Callable[[], Awaitable[T]], *, deadline_s: float) -> T:
    try:
        async with asyncio.timeout(deadline_s):
            return await func()
    except TimeoutError as exc:
        raise DeadlineExceeded() from exc