from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class Provider(ABC):
    name: str

    @abstractmethod
    async def chat_completion(self, payload: dict) -> dict: ...

    @abstractmethod
    def stream_chat_completion(self, payload: dict) -> AsyncIterator[dict]: ...

    @abstractmethod
    async def aclose(self) -> None: ...