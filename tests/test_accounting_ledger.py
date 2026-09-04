import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select

from switchboard.accounting.ledger import record_usage
from switchboard.db.models import Model, RequestRecord, Tenant, UsageDaily


async def test_record_usage_creates_request_and_usage_daily_rows(db_session) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    await db_session.flush()

    try:
        record = await record_usage(
            db_session, tenant.id, "gpt-4o-mini", {"prompt_tokens": 1000, "completion_tokens": 500}
        )
        assert record is not None
        assert record.cost_micros == 450

        today = datetime.now(UTC).date()
        rollup = await db_session.scalar(
            select(UsageDaily).where(UsageDaily.tenant_id == tenant.id, UsageDaily.day == today)
        )
        assert rollup is not None
        assert rollup.requests == 1
        assert rollup.tokens_in == 1000
        assert rollup.tokens_out == 500
        assert rollup.cost_micros == 450
    finally:
        await db_session.execute(delete(RequestRecord).where(RequestRecord.tenant_id == tenant.id))
        await db_session.execute(delete(UsageDaily).where(UsageDaily.tenant_id == tenant.id))
        await db_session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db_session.commit()


async def test_record_usage_accumulates_usage_daily_across_calls(db_session) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    db_session.add(tenant)
    await db_session.flush()

    try:
        await record_usage(
            db_session, tenant.id, "gpt-4o-mini", {"prompt_tokens": 1000, "completion_tokens": 500}
        )
        await record_usage(
            db_session, tenant.id, "gpt-4o-mini", {"prompt_tokens": 200, "completion_tokens": 100}
        )

        today = datetime.now(UTC).date()
        rollup = await db_session.scalar(
            select(UsageDaily).where(UsageDaily.tenant_id == tenant.id, UsageDaily.day == today)
        )
        assert rollup is not None
        assert rollup.requests == 2
        assert rollup.tokens_in == 1200
        assert rollup.tokens_out == 600
        assert rollup.cost_micros == 540
    finally:
        await db_session.execute(delete(RequestRecord).where(RequestRecord.tenant_id == tenant.id))
        await db_session.execute(delete(UsageDaily).where(UsageDaily.tenant_id == tenant.id))
        await db_session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db_session.commit()


async def test_historical_cost_is_unaffected_by_later_price_changes(db_session) -> None:
    tenant = Tenant(name=f"tenant-{uuid.uuid4()}")
    model = Model(
        provider="test",
        model_name=f"test-model-{uuid.uuid4()}",
        input_cost_per_mtok=100_000,
        output_cost_per_mtok=200_000,
    )
    db_session.add_all([tenant, model])
    await db_session.flush()

    try:
        record = await record_usage(
            db_session,
            tenant.id,
            model.model_name,
            {"prompt_tokens": 1000, "completion_tokens": 500},
        )
        assert record is not None
        assert record.cost_micros == 200

        model.input_cost_per_mtok = 999_999_999
        model.output_cost_per_mtok = 999_999_999
        await db_session.commit()

        await db_session.refresh(record)
        assert record.cost_micros == 200
    finally:
        await db_session.execute(delete(RequestRecord).where(RequestRecord.tenant_id == tenant.id))
        await db_session.execute(delete(UsageDaily).where(UsageDaily.tenant_id == tenant.id))
        await db_session.execute(delete(Model).where(Model.id == model.id))
        await db_session.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db_session.commit()