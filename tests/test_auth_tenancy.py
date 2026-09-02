import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from switchboard.auth.keys import generate_api_key
from switchboard.auth.tenancy import AuthenticationError, authenticate
from switchboard.db.models import ApiKey, Tenant


async def _make_tenant_with_key(
    session: AsyncSession, *, revoked: bool = False
) -> tuple[Tenant, str]:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    session.add(tenant)
    await session.flush()

    generated = generate_api_key()
    api_key = ApiKey(
        tenant_id=tenant.id,
        key_prefix=generated.key_prefix,
        key_hash=generated.key_hash,
        revoked_at=datetime.now(UTC) if revoked else None,
    )
    session.add(api_key)
    await session.flush()
    return tenant, generated.key


async def test_authenticate_accepts_valid_key(db_session: AsyncSession) -> None:
    tenant, key = await _make_tenant_with_key(db_session)
    result = await authenticate(db_session, f"Bearer {key}")
    assert result.id == tenant.id


async def test_authenticate_rejects_wrong_key(db_session: AsyncSession) -> None:
    await _make_tenant_with_key(db_session)
    with pytest.raises(AuthenticationError):
        await authenticate(db_session, "Bearer sbk_totally-made-up")


async def test_authenticate_rejects_revoked_key(db_session: AsyncSession) -> None:
    _, key = await _make_tenant_with_key(db_session, revoked=True)
    with pytest.raises(AuthenticationError):
        await authenticate(db_session, f"Bearer {key}")


async def test_authenticate_rejects_missing_header(db_session: AsyncSession) -> None:
    with pytest.raises(AuthenticationError):
        await authenticate(db_session, None)


async def test_authenticate_rejects_malformed_header(db_session: AsyncSession) -> None:
    with pytest.raises(AuthenticationError):
        await authenticate(db_session, "NotBearer something")