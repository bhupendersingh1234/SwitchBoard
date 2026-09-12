from collections.abc import AsyncIterator
import httpx
from switchboard.providers.base import Provider


def _is_client_error(exc: Exception) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500


class FailoverProvider(Provider):
    name = "failover"

    def __init__(self, providers: list[Provider]) -> None:
        if not providers:
            raise ValueError("FailoverProvider needs at least one provider")
        self._providers = providers

    async def chat_completion(self, payload: dict) -> dict:
        last_exc: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.chat_completion(payload)
            except Exception as exc:
                if _is_client_error(exc):
                    raise
                last_exc = exc
        assert last_exc is not None
        raise last_exc

    def stream_chat_completion(self, payload: dict) -> AsyncIterator[dict]:
        # Only the first provider streams. Falling over to a second provider after
        # the first has already sent chunks would produce a response that's the
        # concatenation of two different completions - worse than just failing.
        return self._providers[0].stream_chat_completion(payload)

    async def aclose(self) -> None:
        for provider in self._providers:
            await provider.aclose()