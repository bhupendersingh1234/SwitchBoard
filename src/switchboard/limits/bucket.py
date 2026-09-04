from pathlib import Path

from redis.asyncio import Redis

_SCRIPT_SOURCE = (Path(__file__).parent / "bucket.lua").read_text()


class TokenBucket:
    def __init__(self, redis: Redis) -> None:
        self._script = redis.register_script(_SCRIPT_SOURCE)

    async def consume(
        self, key: str, capacity: int, refill_per_second: float, now: float, cost: int = 1
    ) -> tuple[bool, float]:
        allowed, remaining = await self._script(
            keys=[key], args=[capacity, refill_per_second, now, cost]
        )
        return bool(int(allowed)), float(remaining)