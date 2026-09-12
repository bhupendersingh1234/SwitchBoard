import json

from redis.asyncio import Redis


async def get_cached_response(redis: Redis, key: str) -> dict | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    result: dict = json.loads(raw)
    return result


async def set_cached_response(redis: Redis, key: str, response: dict, ttl_s: int) -> None:
    await redis.set(key, json.dumps(response), ex=ttl_s)