import httpx
import pytest

from switchboard.providers.openai import OpenAIProvider


async def test_chat_completion_returns_upstream_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "chatcmpl-1", "choices": []})

    provider = OpenAIProvider(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    result = await provider.chat_completion({"model": "gpt-4", "messages": []})
    assert result["id"] == "chatcmpl-1"
    await provider.aclose()


async def test_chat_completion_propagates_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream too slow", request=request)

    provider = OpenAIProvider(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(httpx.ReadTimeout):
        await provider.chat_completion({"model": "gpt-4", "messages": []})
    await provider.aclose()