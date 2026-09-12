from switchboard.cache.exact import get_cached_response, set_cached_response


async def test_get_returns_none_when_not_cached(redis) -> None:
    result = await get_cached_response(redis, "cache:missing-key")
    assert result is None


async def test_set_then_get_round_trips_the_response(redis) -> None:
    response = {"id": "chatcmpl-cached", "choices": []}
    await set_cached_response(redis, "cache:test-key", response, ttl_s=60)

    result = await get_cached_response(redis, "cache:test-key")
    assert result == response