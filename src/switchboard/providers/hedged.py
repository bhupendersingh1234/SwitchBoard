import asyncio

from switchboard.providers.base import Provider


class HedgedProvider(Provider):
    def __init__(self, primary: Provider, backup: Provider, *, hedge_delay: float = 0.15) -> None:
        self.name = primary.name
        self._primary = primary
        self._backup = backup
        self._hedge_delay = hedge_delay

    async def chat_completion(self, payload: dict) -> dict:
        primary_task = asyncio.ensure_future(self._primary.chat_completion(payload))
        done, _ = await asyncio.wait({primary_task}, timeout=self._hedge_delay)
        if primary_task in done and primary_task.exception() is None:
            return primary_task.result()

        backup_task = asyncio.ensure_future(self._backup.chat_completion(payload))
        pending = {t for t in (primary_task, backup_task) if not t.done()}

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task.exception() is None:
                    for remaining in pending:
                        remaining.cancel()
                    return task.result()

        primary_exc = primary_task.exception()
        if primary_exc is not None:
            raise primary_exc
        backup_exc = backup_task.exception()
        assert backup_exc is not None
        raise backup_exc

    async def aclose(self) -> None:
        await self._primary.aclose()
        await self._backup.aclose()