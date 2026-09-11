import asyncio

import pytest

from switchboard.resilience.timeouts import DeadlineExceeded, with_deadline


async def test_fast_function_completes_within_deadline() -> None:
    async def fast() -> str:
        return "ok"

    result = await with_deadline(fast, deadline_s=1.0)
    assert result == "ok"


async def test_slow_function_raises_deadline_exceeded() -> None:
    async def slow() -> str:
        await asyncio.sleep(1.0)
        return "unreachable"

    with pytest.raises(DeadlineExceeded):
        await with_deadline(slow, deadline_s=0.05)