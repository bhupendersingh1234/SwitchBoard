import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete

from switchboard.db.models import Model, Tenant, UsageDaily
from switchboard.limits.budget import BudgetExceeded, enforce_budget, get_monthly_spend_micros


async def test_get_monthly_spend_micros_sums_current_month_only(db_session) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    model = Model(
        provider="test",
        model_name=f"test-model-{uuid.uuid4()}",
        input_cost_per_mtok=1,
        output_cost_per_mtok=1,
    )
    db_session.add_all([tenant, model])
    await db_session.flush()

    now = datetime.now(UTC)
    this_month = now.date().replace(day=1)
    last_month = (this_month.replace(day=1) - date.resolution).replace(day=1)

    db_session.add_all(
        [
            UsageDaily(
                tenant_id=tenant.id,
                day=this_month,
                model_id=model.id,
                requests=1,
                tokens_in=0,
                tokens_out=0,
                cost_micros=300,
            ),
            UsageDaily(
                tenant_id=tenant.id,
                day=last_month,
                model_id=model.id,
                requests=1,
                tokens_in=0,
                tokens_out=0,
                cost_micros=999_999,
            ),
        ]
    )
    await db_session.flush()

    try:
        spend = await get_monthly_spend_micros(db_session, tenant.id, now=now)
        assert spend == 300
    finally:
        await db_session.execute(delete(UsageDaily).where(UsageDaily.tenant_id == tenant.id))
        await db_session.execute(delete(Model).where(Model.id == model.id))
        await db_session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db_session.commit()


async def test_enforce_budget_allows_when_none_configured(db_session) -> None:
    tenant_id = uuid.uuid4()
    await enforce_budget(db_session, tenant_id, monthly_budget_micros=None)


async def test_enforce_budget_raises_when_spend_meets_or_exceeds_cap(db_session) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    model = Model(
        provider="test",
        model_name=f"test-model-{uuid.uuid4()}",
        input_cost_per_mtok=1,
        output_cost_per_mtok=1,
    )
    db_session.add_all([tenant, model])
    await db_session.flush()

    db_session.add(
        UsageDaily(
            tenant_id=tenant.id,
            day=datetime.now(UTC).date(),
            model_id=model.id,
            requests=1,
            tokens_in=0,
            tokens_out=0,
            cost_micros=1000,
        )
    )
    await db_session.flush()

    try:
        with pytest.raises(BudgetExceeded):
            await enforce_budget(db_session, tenant.id, monthly_budget_micros=1000)
        await enforce_budget(db_session, tenant.id, monthly_budget_micros=1001)
    finally:
        await db_session.execute(delete(UsageDaily).where(UsageDaily.tenant_id == tenant.id))
        await db_session.execute(delete(Model).where(Model.id == model.id))
        await db_session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db_session.commit()