import asyncio

import httpx
import pytest

from switchboard.providers.base import Provider
from switchboard.providers.failover import FailoverProvider
from switchboard.providers.resilient import ResilientProvider
from switchboard.resilience.breaker import CircuitBreaker
from switchboard.resilience.timeouts import DeadlineExceeded, with_deadline


class _AlwaysFailsProvider(Provider):
    name = "primary"

    async def chat_completion(self, payload: dict) -> dict:
        raise httpx.ConnectError(
            "simulated outage", request=httpx.Request("POST", "https://primary.example.com")
        )

    def stream_chat_completion(self, payload: dict):
        raise NotImplementedError("not exercised by these tests")

    async def aclose(self) -> None:
        pass


class _HealthyProvider(Provider):
    name = "backup"

    async def chat_completion(self, payload: dict) -> dict:
        return {"id": "chatcmpl-backup", "choices": []}

    def stream_chat_completion(self, payload: dict):
        raise NotImplementedError("not exercised by these tests")

    async def aclose(self) -> None:
        pass


class _AlwaysSlowProvider(Provider):
    name = "slow"

    async def chat_completion(self, payload: dict) -> dict:
        await asyncio.sleep(5.0)
        return {"id": "should never get here"}

    def stream_chat_completion(self, payload: dict):
        raise NotImplementedError("not exercised by these tests")

    async def aclose(self) -> None:
        pass


async def test_injected_primary_outage_fails_over_within_deadline() -> None:
    primary = ResilientProvider(
        _AlwaysFailsProvider(),
        breaker=CircuitBreaker(failure_threshold=10, recovery_timeout=30.0),
        max_attempts=2,
    )
    backup = ResilientProvider(_HealthyProvider(), breaker=CircuitBreaker())
    provider = FailoverProvider([primary, backup])

    result = await with_deadline(lambda: provider.chat_completion({}), deadline_s=2.0)

    assert result == {"id": "chatcmpl-backup", "choices": []}


async def test_deadline_is_enforced_even_when_every_provider_is_slow() -> None:
    provider = FailoverProvider([_AlwaysSlowProvider(), _AlwaysSlowProvider()])

    with pytest.raises(DeadlineExceeded):
        await with_deadline(lambda: provider.chat_completion({}), deadline_s=0.2)