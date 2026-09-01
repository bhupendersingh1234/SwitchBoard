from abc import ABC, abstractmethod


class Provider(ABC):
    name: str

    @abstractmethod
    async def chat_completion(self, payload: dict) -> dict: ...

    @abstractmethod
    async def aclose(self) -> None: ...