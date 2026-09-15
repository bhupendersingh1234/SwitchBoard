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

    def __init__(self, wrapped: Provider, *, models: list[str]) -> None:
        if not models:
            raise ValueError("CascadeProvider requires at least one model")
        self._wrapped = wrapped
        self._models = models

    async def chat_completion(self, payload: dict) -> dict:
        response, _legs = await self.chat_completion_with_legs(payload)
        return response

    async def chat_completion_with_legs(self, payload: dict) -> tuple[dict, list[CascadeLeg]]:
        legs: list[CascadeLeg] = []
        for i, model in enumerate(self._models):
            response = await self._wrapped.chat_completion({**payload, "model": model})
            legs.append(CascadeLeg(model=model, usage=response.get("usage", {})))
            is_last_tier = i == len(self._models) - 1
            if is_last_tier or not is_low_quality(response):
                return response, legs
        raise AssertionError("unreachable: the loop above always returns on its last iteration")

    def stream_chat_completion(self, payload: dict) -> AsyncIterator[dict]:
        # The quality check needs finish_reason, which only exists once a response
        # is complete - by definition not available mid-stream. Cascade can't
        # un-send tokens any more than retry or failover could (M6). Streaming
        # under the cascade model just gets the cheapest tier directly, un-escalated.
        return self._wrapped.stream_chat_completion({**payload, "model": self._models[0]})

    async def aclose(self) -> None:
        await self._wrapped.aclose()