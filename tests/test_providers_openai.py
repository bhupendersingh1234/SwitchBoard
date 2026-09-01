import httpx

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