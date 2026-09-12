from collections.abc import AsyncIterator

class _TrackedProviderStream:
    def __init__(self, chunks: list[dict]) -> None:
        self._chunks = chunks
        self.closed = False

    async def __aiter__(self):
        try:
            for chunk in self._chunks:
                yield chunk
        finally:
            self.closed = True

    def aclose(self):
        return self.__aiter__().aclose()


def _make_event_generator_with_trackable_upstream(
    upstream, recorded: list[dict]
) -> AsyncIterator[bytes]:
    async def event_generator() -> AsyncIterator[bytes]:
        usage: dict = {}
        stream = upstream.__aiter__()
        try:
            async for chunk in stream:
                if chunk.get("usage"):
                    usage = chunk["usage"]
                yield f"data: {chunk}\n\n".encode()
            yield b"data: [DONE]\n\n"
        finally:
            await stream.aclose()
            if usage:
                recorded.append(usage)

    return event_generator()


async def test_client_disconnect_immediately_closes_upstream_stream() -> None:
    upstream = _TrackedProviderStream(
        [
            {"choices": [{"delta": {"content": "hi"}}]},
            {"choices": [{"delta": {"content": "more"}}]},
            {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        ]
    )
    recorded: list[dict] = []
    gen = _make_event_generator_with_trackable_upstream(upstream, recorded)

    await anext(gen)
    assert upstream.closed is False

    await gen.aclose()
    assert upstream.closed is True