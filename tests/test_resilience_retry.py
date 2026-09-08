import httpx
import pytest

from switchboard.resilience.retry import retry_with_jitter


async def test_retry_returns_immediately_on_first_success() -> None:
    calls = 0

    async def func() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await retry_with_jitter(func, retryable=(httpx.TimeoutException,))
    assert result == "ok"
    assert calls == 1


async def test_retry_succeeds_after_transient_failures() -> None:
    calls = 0
    delays: list[float] = []

    async def func() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ReadTimeout("slow", request=httpx.Request("POST", "https://example.com"))
        return "ok"

    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    result = await retry_with_jitter(
        func, retryable=(httpx.TimeoutException,), max_attempts=5, sleep=sleep
    )
    assert result == "ok"
    assert calls == 3
    assert len(delays) == 2


async def test_retry_raises_after_exhausting_max_attempts() -> None:
    calls = 0

    async def func() -> str:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow", request=httpx.Request("POST", "https://example.com"))

    async def sleep(seconds: float) -> None:
        return None

    with pytest.raises(httpx.ReadTimeout):
        await retry_with_jitter(
            func, retryable=(httpx.TimeoutException,), max_attempts=3, sleep=sleep
        )
    assert calls == 3


async def test_retry_does_not_retry_non_retryable_exceptions() -> None:
    calls = 0

    async def func() -> str:
        nonlocal calls
        calls += 1
        raise ValueError("not a transient error")

    with pytest.raises(ValueError):
        await retry_with_jitter(func, retryable=(httpx.TimeoutException,), max_attempts=3)
    assert calls == 1


def _make_recording_sleep(delays: list[float]):
    async def sleep(seconds: float) -> None:
        delays.append(seconds)

    return sleep


async def test_retry_delays_are_jittered_not_fixed() -> None:
    delays_seen: set[float] = set()

    for _ in range(20):
        calls = 0
        delays: list[float] = []

        async def func() -> str:
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("slow", request=httpx.Request("POST", "https://example.com"))

        with pytest.raises(httpx.ReadTimeout):
            await retry_with_jitter(
                func,
                retryable=(httpx.TimeoutException,),
                max_attempts=2,
                base_delay=1.0,
                sleep=_make_recording_sleep(delays),
            )
        assert 0.0 <= delays[0] <= 1.0
        delays_seen.add(delays[0])

    assert len(delays_seen) > 1