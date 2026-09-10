import httpx
import pytest

from switchboard.providers.base import Provider
from switchboard.providers.resilient import ResilientProvider
from switchboard.resilience.breaker import CircuitBreaker, CircuitOpenError


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


class _ScriptedProvider(Provider):
    name = "scripted"

    def __init__(self, outcomes: list) -> None:
        self._outcomes = outcomes
        self.calls = 0

    async def chat_completion(self, payload: dict) -> dict:
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def aclose(self) -> None:
        pass


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.com/v1/chat/completions")
    response = httpx.Response(status, json={"error": "boom"}, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


async def test_succeeds_immediately_when_wrapped_provider_succeeds() -> None:
    wrapped = _ScriptedProvider([{"id": "ok"}])
    provider = ResilientProvider(wrapped)

    result = await provider.chat_completion({})
    assert result == {"id": "ok"}
    assert wrapped.calls == 1


async def test_retries_transient_timeout_then_succeeds() -> None:
    wrapped = _ScriptedProvider(
        [
            httpx.ReadTimeout("slow", request=httpx.Request("POST", "https://example.com")),
            {"id": "ok"},
        ]
    )
    provider = ResilientProvider(wrapped)

    result = await provider.chat_completion({})
    assert result == {"id": "ok"}
    assert wrapped.calls == 2


async def test_does_not_retry_client_error() -> None:
    wrapped = _ScriptedProvider([_http_error(400), {"id": "should not reach here"}])
    provider = ResilientProvider(wrapped)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await provider.chat_completion({})
    assert exc_info.value.response.status_code == 400
    assert wrapped.calls == 1


async def test_server_error_retries_and_unwraps_to_original_on_final_failure() -> None:
    wrapped = _ScriptedProvider([_http_error(500), _http_error(500), _http_error(500)])
    breaker = CircuitBreaker(failure_threshold=10, recovery_timeout=30.0)
    provider = ResilientProvider(wrapped, breaker=breaker)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await provider.chat_completion({})
    assert exc_info.value.response.status_code == 500
    assert wrapped.calls == 3


async def test_repeated_server_errors_open_circuit_and_fail_fast() -> None:
    clock = _FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0, clock=clock)
    wrapped = _ScriptedProvider([_http_error(500)] * 10)
    provider = ResilientProvider(wrapped, breaker=breaker)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.chat_completion({})
    assert wrapped.calls == 3

    with pytest.raises(CircuitOpenError):
        await provider.chat_completion({})
    assert wrapped.calls == 3