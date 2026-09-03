import uuid

from sqlalchemy import delete

from switchboard.auth.keys import generate_api_key
from switchboard.db.models import ApiKey, Tenant


async def test_keys_endpoint_only_returns_own_tenants_keys(live_client, db_session) -> None:
    tenant_a = Tenant(name=f"tenant-a-{uuid.uuid4()}")
    tenant_b = Tenant(name=f"tenant-b-{uuid.uuid4()}")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()

    key_a = generate_api_key()
    key_b = generate_api_key()
    db_session.add_all(
        [
            ApiKey(tenant_id=tenant_a.id, key_prefix=key_a.key_prefix, key_hash=key_a.key_hash),
            ApiKey(tenant_id=tenant_b.id, key_prefix=key_b.key_prefix, key_hash=key_b.key_hash),
        ]
    )
    await db_session.commit()

    try:
        response_a = await live_client.get(
            "/keys", headers={"Authorization": f"Bearer {key_a.key}"}
        )
        response_b = await live_client.get(
            "/keys", headers={"Authorization": f"Bearer {key_b.key}"}
        )

        assert response_a.status_code == 200
        assert {item["key_prefix"] for item in response_a.json()} == {key_a.key_prefix}

        assert response_b.status_code == 200
        assert {item["key_prefix"] for item in response_b.json()} == {key_b.key_prefix}
    finally:
        await db_session.execute(
            delete(ApiKey).where(ApiKey.tenant_id.in_([tenant_a.id, tenant_b.id]))
        )
        await db_session.execute(delete(Tenant).where(Tenant.id.in_([tenant_a.id, tenant_b.id])))
        await db_session.commit()