import asyncio

import pytest

from switchboard.resilience.breaker import CircuitBreaker, CircuitOpenError, CircuitState


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


async def test_closed_circuit_allows_calls_through() -> None:
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)

    async def ok() -> str:
        return "ok"

    result = await breaker.call(ok, failure_exceptions=(ValueError,))
    assert result == "ok"
    assert breaker.state == CircuitState.CLOSED


async def test_circuit_opens_after_failure_threshold() -> None:
    clock = _FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0, clock=clock)

    async def fail() -> str:
        raise ValueError("boom")

    for _ in range(3):
        with pytest.raises(ValueError):
            await breaker.call(fail, failure_exceptions=(ValueError,))

    assert breaker.state == CircuitState.OPEN

    calls = 0

    async def should_not_run() -> str:
        nonlocal calls
        calls += 1
        return "unreachable"

    with pytest.raises(CircuitOpenError):
        await breaker.call(should_not_run, failure_exceptions=(ValueError,))
    assert calls == 0


async def test_circuit_moves_to_half_open_after_recovery_timeout() -> None:
    clock = _FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, clock=clock)

    async def fail() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await breaker.call(fail, failure_exceptions=(ValueError,))
    assert breaker.state == CircuitState.OPEN

    clock.now += 10.0
    assert breaker.state == CircuitState.HALF_OPEN


async def test_successful_half_open_trial_closes_circuit() -> None:
    clock = _FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, clock=clock)

    async def fail() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await breaker.call(fail, failure_exceptions=(ValueError,))
    clock.now += 10.0

    async def ok() -> str:
        return "recovered"

    result = await breaker.call(ok, failure_exceptions=(ValueError,))
    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED


async def test_failed_half_open_trial_reopens_circuit() -> None:
    clock = _FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, clock=clock)

    async def fail() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await breaker.call(fail, failure_exceptions=(ValueError,))
    clock.now += 10.0

    with pytest.raises(ValueError):
        await breaker.call(fail, failure_exceptions=(ValueError,))
    assert breaker.state == CircuitState.OPEN


async def test_non_failure_exceptions_do_not_trip_the_circuit() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0)

    async def raises_unrelated() -> str:
        raise KeyError("not a provider failure")

    with pytest.raises(KeyError):
        await breaker.call(raises_unrelated, failure_exceptions=(ValueError,))
    assert breaker.state == CircuitState.CLOSED


async def test_only_one_concurrent_trial_admitted_during_half_open() -> None:
    clock = _FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0, clock=clock)

    async def fail() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await breaker.call(fail, failure_exceptions=(ValueError,))
    clock.now += 10.0

    admitted = 0
    rejected = 0

    async def slow_trial() -> str:
        nonlocal admitted
        admitted += 1
        await asyncio.sleep(0.05)
        return "ok"

    async def attempt() -> None:
        nonlocal rejected
        try:
            await breaker.call(slow_trial, failure_exceptions=(ValueError,))
        except CircuitOpenError:
            rejected += 1

    await asyncio.gather(*[attempt() for _ in range(20)])

    assert admitted == 1
    assert rejected == 19


async def _naive_half_open_gate(state: dict) -> bool:
    if state["trial_in_flight"]:
        return False
    await asyncio.sleep(0)
    state["trial_in_flight"] = True
    return True


async def test_naive_check_then_set_admits_multiple_trials_under_concurrency() -> None:
    state = {"trial_in_flight": False}
    results = await asyncio.gather(*[_naive_half_open_gate(state) for _ in range(20)])
    admitted = sum(1 for r in results if r)
    assert admitted > 1