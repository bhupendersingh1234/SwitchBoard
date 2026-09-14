from collections.abc import AsyncIterator
from dataclasses import dataclass

from switchboard.providers.base import Provider
from switchboard.routing.quality import is_low_quality


@dataclass
class CascadeLeg:
    model: str
    usage: dict


class CascadeProvider(Provider):
    name = "cascade"

    def __init__(self, wrapped: Provider, *, cheap_model: str, expensive_model: str) -> None:
        self._wrapped = wrapped
        self._cheap_model = cheap_model
        self._expensive_model = expensive_model

    async def chat_completion(self, payload: dict) -> dict:
        response, _legs = await self.chat_completion_with_legs(payload)
        return response

    async def chat_completion_with_legs(self, payload: dict) -> tuple[dict, list[CascadeLeg]]:
        cheap_response = await self._wrapped.chat_completion(
            {**payload, "model": self._cheap_model}
        )
        legs = [CascadeLeg(model=self._cheap_model, usage=cheap_response.get("usage", {}))]
        if not is_low_quality(cheap_response):
            return cheap_response, legs

        expensive_response = await self._wrapped.chat_completion(
            {**payload, "model": self._expensive_model}
        )
        legs.append(
            CascadeLeg(model=self._expensive_model, usage=expensive_response.get("usage", {}))
        )
        return expensive_response, legs

    def stream_chat_completion(self, payload: dict) -> AsyncIterator[dict]:
        # The quality check needs finish_reason, which only exists once a response
        # is complete - by definition not available mid-stream. Cascade can't
        # un-send tokens any more than retry or failover could (M6). Streaming
        # under the cascade model just gets the cheap model directly, un-escalated.
        return self._wrapped.stream_chat_completion({**payload, "model": self._cheap_model})

    async def aclose(self) -> None:
        await self._wrapped.aclose()