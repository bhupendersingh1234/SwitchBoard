import uuid

from switchboard.cache.keys import compute_cache_key, is_cacheable


def test_is_cacheable_requires_zero_temperature() -> None:
    assert is_cacheable({"temperature": 0, "messages": []}) is True
    assert is_cacheable({"temperature": 0.7, "messages": []}) is False
    assert is_cacheable({"messages": []}) is False


def test_is_cacheable_excludes_streaming_even_at_zero_temperature() -> None:
    assert is_cacheable({"temperature": 0, "stream": True}) is False


def test_identical_requests_for_same_tenant_produce_same_key() -> None:
    tenant_id = uuid.uuid4()
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0,
    }

    assert compute_cache_key(tenant_id, payload) == compute_cache_key(tenant_id, dict(payload))


def test_different_tenants_get_different_keys_for_the_same_payload() -> None:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0,
    }

    key_a = compute_cache_key(uuid.uuid4(), payload)
    key_b = compute_cache_key(uuid.uuid4(), payload)

    assert key_a != key_b


def test_different_messages_produce_different_keys() -> None:
    tenant_id = uuid.uuid4()
    base = {"model": "gpt-4o-mini", "temperature": 0}

    key_a = compute_cache_key(tenant_id, {**base, "messages": [{"role": "user", "content": "hi"}]})
    key_b = compute_cache_key(tenant_id, {**base, "messages": [{"role": "user", "content": "bye"}]})

    assert key_a != key_b