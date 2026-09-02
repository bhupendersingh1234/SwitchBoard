from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from switchboard.auth.keys import KEY_PREFIX_LENGTH, verify_api_key
from switchboard.db.models import ApiKey, Tenant


class AuthenticationError(Exception):
    pass


async def authenticate(session: AsyncSession, authorization: str | None) -> Tenant:
    if authorization is None or not authorization.startswith("Bearer "):
        raise AuthenticationError("missing or malformed Authorization header")

    key = authorization.removeprefix("Bearer ").strip()
    if len(key) < KEY_PREFIX_LENGTH:
        raise AuthenticationError("invalid api key")

    row = await session.scalar(select(ApiKey).where(ApiKey.key_prefix == key[:KEY_PREFIX_LENGTH]))
    if row is None or row.revoked_at is not None or not verify_api_key(key, row.key_hash):
        raise AuthenticationError("invalid api key")

    tenant = await session.get(Tenant, row.tenant_id)
    if tenant is None:
        raise AuthenticationError("invalid api key")
    return tenant