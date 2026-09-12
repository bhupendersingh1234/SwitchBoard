import httpx

from switchboard.providers.openai import OpenAIProvider


async def test_stream_chat_completion_yields_parsed_chunks_and_stops_at_done() -> None:
    sse_body = (
        b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body, headers={"content-type": "text/event-stream"})

    provider = OpenAIProvider(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    chunks = [chunk async for chunk in provider.stream_chat_completion({"model": "gpt-4o-mini"})]

    assert chunks == [
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
    ]
    await provider.aclose()


async def test_stream_chat_completion_raises_on_error_status_before_yielding() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    provider = OpenAIProvider(
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    chunks = []
    raised = False
    try:
        async for chunk in provider.stream_chat_completion({"model": "gpt-4o-mini"}):
            chunks.append(chunk)
    except httpx.HTTPStatusError as exc:
        raised = True
        assert exc.response.status_code == 429

    assert raised
    assert chunks == []
    await provider.aclose()