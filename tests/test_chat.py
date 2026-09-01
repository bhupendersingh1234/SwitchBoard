import httpx
import pytest

from switchboard.api.deps import get_resources
from switchboard.main import app


class _StubProvider:
    name = "stub"

    async def chat_completion(self, payload: dict) -> dict:
        return {"id": "chatcmpl-stub", "choices": []}


class _StubResources:
    provider = _StubProvider()


class _FailingProvider:
    name = "stub"

    async def chat_completion(self, payload: dict) -> dict:
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        response = httpx.Response(400, json={"error": {"message": "bad request"}}, request=request)
        raise httpx.HTTPStatusError("bad request", request=request, response=response)


class _FailingResources:
    provider = _FailingProvider()


@pytest.fixture
def stub_resources():
    app.dependency_overrides[get_resources] = lambda: _StubResources()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def failing_resources():
    app.dependency_overrides[get_resources] = lambda: _FailingResources()
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