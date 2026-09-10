import httpx

from switchboard.providers.base import Provider
from switchboard.resilience.breaker import CircuitBreaker
from switchboard.resilience.retry import retry_with_jitter


class ProviderServerError(Exception):
    def __init__(self, original: httpx.HTTPStatusError) -> None:
        self.original = original
        super().__init__(str(original))


_RETRYABLE = (httpx.TimeoutException, httpx.ConnectError, ProviderServerError)


class ResilientProvider(Provider):
    def __init__(
        self,
        wrapped: Provider,
        *,
        breaker: CircuitBreaker | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.name = wrapped.name
        self._wrapped = wrapped
        self._breaker = breaker or CircuitBreaker()
        self._max_attempts = max_attempts

    async def _attempt(self, payload: dict) -> dict:
        async def call_wrapped() -> dict:
            try:
                return await self._wrapped.chat_completion(payload)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500:
                    raise ProviderServerError(exc) from exc
                raise

        return await self._breaker.call(call_wrapped, failure_exceptions=_RETRYABLE)

    async def chat_completion(self, payload: dict) -> dict:
        try:
            return await retry_with_jitter(
                lambda: self._attempt(payload),
                retryable=_RETRYABLE,
                max_attempts=self._max_attempts,
            )
        except ProviderServerError as exc:
            raise exc.original from exc

    async def aclose(self) -> None:
        await self._wrapped.aclose()