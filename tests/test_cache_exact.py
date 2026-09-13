import uuid 
from switchboard.cache.exact import get_cached_response, set_cached_response
from switchboard.cache.keys import compute_cache_key


async def test_get_returns_none_when_not_cached(redis) -> None:
    result = await get_cached_response(redis, "cache:missing-key")
    assert result is None


async def test_set_then_get_round_trips_the_response(redis) -> None:
    response = {"id": "chatcmpl-cached", "choices": []}
    await set_cached_response(redis, "cache:test-key", response, ttl_s=60)

    result = await get_cached_response(redis, "cache:test-key")
    assert result == response


async def test_tenant_isolation_through_the_full_key_and_cache_composition(redis) -> None:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0,
    }
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    key_a = compute_cache_key(tenant_a, payload)
    await set_cached_response(redis, key_a, {"id": "belongs-to-a"}, ttl_s=60)

    key_b = compute_cache_key(tenant_b, payload)
    result_for_b = await get_cached_response(redis, key_b)

    assert result_for_b is None
    assert await get_cached_response(redis, key_a) == {"id": "belongs-to-a"}