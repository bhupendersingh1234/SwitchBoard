import httpx

from switchboard.providers.base import Provider


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_s: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(connect=5.0, read=timeout_s, write=5.0, pool=5.0),
            transport=transport,
        )

    async def chat_completion(self, payload: dict) -> dict:
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        result: dict = response.json()
        return result

    async def aclose(self) -> None:
        await self._client.aclose()