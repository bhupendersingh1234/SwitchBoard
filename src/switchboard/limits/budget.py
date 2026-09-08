import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from switchboard.db.models import UsageDaily


class BudgetExceeded(Exception):
    pass


async def get_monthly_spend_micros(
    session: AsyncSession, tenant_id: uuid.UUID, now: datetime | None = None
) -> int:
    if now is None:
        now = datetime.now(UTC)
    month_start = now.date().replace(day=1)
    total = await session.scalar(
        select(func.coalesce(func.sum(UsageDaily.cost_micros), 0)).where(
            UsageDaily.tenant_id == tenant_id, UsageDaily.day >= month_start
        )
    )
    return int(total) if total is not None else 0


async def enforce_budget(
    session: AsyncSession, tenant_id: uuid.UUID, monthly_budget_micros: int | None
) -> None:
    if monthly_budget_micros is None:
        return
    spent = await get_monthly_spend_micros(session, tenant_id)
    if spent >= monthly_budget_micros:
        raise BudgetExceeded()