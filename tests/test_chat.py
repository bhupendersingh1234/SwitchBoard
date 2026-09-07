import httpx
import pytest

from switchboard.api.deps import (
    check_rate_limit,
    get_current_tenant,
    get_resources,
    get_session,
    reserve_tpm,
)
from switchboard.core.config import get_settings
from switchboard.db.models import Tenant
from switchboard.main import app

_FAKE_TENANT = Tenant(name="test-tenant")


class _NoOpSession:
    async def scalar(self, *args, **kwargs):
        raise RuntimeError("no database in this test")


class _NoOpRateLimiter:
    async def refund(self, *args, **kwargs):
        pass


class _StubProvider:
    name = "stub"

    async def chat_completion(self, payload: dict) -> dict:
        return {"id": "chatcmpl-stub", "choices": []}


class _StubResources:
    provider = _StubProvider()
    settings = get_settings()
    rate_limiter = _NoOpRateLimiter()


class _FailingProvider:
    name = "stub"

    async def chat_completion(self, payload: dict) -> dict:
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        response = httpx.Response(400, json={"error": {"message": "bad request"}}, request=request)
        raise httpx.HTTPStatusError("bad request", request=request, response=response)


class _FailingResources:
    provider = _FailingProvider()
    settings = get_settings()
    rate_limiter = _NoOpRateLimiter()


class _TimeoutProvider:
    name = "stub"

    async def chat_completion(self, payload: dict) -> dict:
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        raise httpx.ReadTimeout("upstream too slow", request=request)


class _TimeoutResources:
    provider = _TimeoutProvider()
    settings = get_settings()
    rate_limiter = _NoOpRateLimiter()


@pytest.fixture
def stub_resources():
    app.dependency_overrides[get_resources] = lambda: _StubResources()
    app.dependency_overrides[get_current_tenant] = lambda: _FAKE_TENANT
    app.dependency_overrides[get_session] = lambda: _NoOpSession()
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[reserve_tpm] = lambda: 100
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def failing_resources():
    app.dependency_overrides[get_resources] = lambda: _FailingResources()
    app.dependency_overrides[get_current_tenant] = lambda: _FAKE_TENANT
    app.dependency_overrides[get_session] = lambda: _NoOpSession()
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[reserve_tpm] = lambda: 100
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def timeout_resources():
    app.dependency_overrides[get_resources] = lambda: _TimeoutResources()
    app.dependency_overrides[get_current_tenant] = lambda: _FAKE_TENANT
    app.dependency_overrides[get_session] = lambda: _NoOpSession()
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[reserve_tpm] = lambda: 100
    yield
    app.dependency_overrides.clear()


async def test_chat_completions_returns_provider_response(client, stub_resources) -> None:
    response = await client.post("/v1/chat/completions", json={"model": "gpt-4", "messages": []})
    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-stub"


async def test_chat_completions_surfaces_upstream_error_status(client, failing_resources) -> None:
    response = await client.post("/v1/chat/completions", json={"model": "gpt-4", "messages": []})
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["message"] == "bad request"


async def test_chat_completions_returns_504_on_upstream_timeout(client, timeout_resources) -> None:
    response = await client.post("/v1/chat/completions", json={"model": "gpt-4", "messages": []})
    assert response.status_code == 504