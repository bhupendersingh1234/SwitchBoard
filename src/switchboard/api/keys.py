from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from switchboard.api.deps import CurrentTenantDep, SessionDep
from switchboard.db.models import ApiKey

router = APIRouter(tags=["keys"])


class ApiKeyOut(BaseModel):
    id: UUID
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None


@router.get("/keys")
async def list_keys(tenant: CurrentTenantDep, session: SessionDep) -> list[ApiKeyOut]:
    rows = await session.scalars(select(ApiKey).where(ApiKey.tenant_id == tenant.id))
    return [
        ApiKeyOut(
            id=row.id,
            key_prefix=row.key_prefix,
            created_at=row.created_at,
            revoked_at=row.revoked_at,
        )
        for row in rows
    ]