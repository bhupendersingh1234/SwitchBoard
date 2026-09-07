import time
import uuid

import httpx
import respx
from sqlalchemy import delete, select

from switchboard.api.deps import get_current_tenant
from switchboard.auth.keys import generate_api_key
from switchboard.core.config import get_settings
from switchboard.db.models import ApiKey, RequestRecord, Tenant, UsageDaily
from switchboard.limits.bucket import TokenBucket
from switchboard.main import app


@respx.mock
async def test_full_app_proxies_chat_completions_through_real_lifespan(live_client) -> None:
    app.dependency_overrides[get_current_tenant] = lambda: Tenant(name="test-tenant")
    try:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"id": "chatcmpl-real", "choices": []})
        )
        response = await live_client.post(
            "/v1/chat/completions", json={"model": "gpt-4", "messages": []}
        )
        assert response.status_code == 200
        assert response.json()["id"] == "chatcmpl-real"
    finally:
        app.dependency_overrides.clear()


async def test_chat_completions_requires_authentication(live_client) -> None:
    response = await live_client.post(
        "/v1/chat/completions", json={"model": "gpt-4", "messages": []}
    )
    assert response.status_code == 401


@respx.mock
async def test_full_app_records_usage_and_cost_for_real_request(live_client, db_session) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    await db_session.flush()

    generated = generate_api_key()
    db_session.add(
        ApiKey(tenant_id=tenant.id, key_prefix=generated.key_prefix, key_hash=generated.key_hash)
    )
    await db_session.commit()

    try:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "chatcmpl-real",
                    "choices": [],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
                },
            )
        )
        response = await live_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": []},
            headers={"Authorization": f"Bearer {generated.key}"},
        )
        assert response.status_code == 200

        record = await db_session.scalar(
            select(RequestRecord).where(RequestRecord.tenant_id == tenant.id)
        )
        assert record is not None
        assert record.prompt_tokens == 1000
        assert record.completion_tokens == 500
        assert record.cost_micros == 450
    finally:
        await db_session.execute(delete(RequestRecord).where(RequestRecord.tenant_id == tenant.id))
        await db_session.execute(delete(UsageDaily).where(UsageDaily.tenant_id == tenant.id))
        await db_session.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant.id))
        await db_session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db_session.commit()


async def test_chat_completions_returns_429_with_retry_after_when_rate_limited(
    live_client, db_session, redis
) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    await db_session.flush()

    generated = generate_api_key()
    db_session.add(
        ApiKey(tenant_id=tenant.id, key_prefix=generated.key_prefix, key_hash=generated.key_hash)
    )
    await db_session.commit()

    try:
        settings = get_settings()
        bucket = TokenBucket(redis)
        now = time.time()
        for _ in range(settings.rpm_limit):
            await bucket.consume(
                key=f"ratelimit:rpm:{tenant.id}",
                capacity=settings.rpm_limit,
                refill_per_second=settings.rpm_limit / 60,
                now=now,
            )

        response = await live_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": []},
            headers={"Authorization": f"Bearer {generated.key}"},
        )
        assert response.status_code == 429
        assert "Retry-After" in response.headers
    finally:
        await db_session.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant.id))
        await db_session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db_session.commit()
        await redis.delete(f"ratelimit:rpm:{tenant.id}")


@respx.mock
async def test_chat_completions_tpm_reservation_reconciles_to_actual_usage(
    live_client, db_session, redis
) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    await db_session.flush()

    generated = generate_api_key()
    db_session.add(
        ApiKey(tenant_id=tenant.id, key_prefix=generated.key_prefix, key_hash=generated.key_hash)
    )
    await db_session.commit()

    try:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "chatcmpl-real",
                    "choices": [],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            )
        )
        response = await live_client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": f"Bearer {generated.key}"},
        )
        assert response.status_code == 200

        settings = get_settings()
        bucket = TokenBucket(redis)
        _, remaining = await bucket.consume(
            key=f"ratelimit:tpm:{tenant.id}",
            capacity=settings.tpm_limit,
            refill_per_second=settings.tpm_limit / 60,
            now=time.time(),
            cost=0,
        )
        consumed = settings.tpm_limit - remaining
        assert abs(consumed - 15) < 50
    finally:
        await db_session.execute(delete(RequestRecord).where(RequestRecord.tenant_id == tenant.id))
        await db_session.execute(delete(UsageDaily).where(UsageDaily.tenant_id == tenant.id))
        await db_session.execute(delete(ApiKey).where(ApiKey.tenant_id == tenant.id))
        await db_session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db_session.commit()
        await redis.delete(f"ratelimit:tpm:{tenant.id}")