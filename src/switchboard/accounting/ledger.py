import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from switchboard.accounting.pricing import compute_cost_micros
from switchboard.db.models import Model, RequestRecord, UsageDaily

log = logging.getLogger(__name__)


async def record_usage(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    model_name: str,
    usage: dict,
) -> RequestRecord | None:
    model = await session.scalar(select(Model).where(Model.model_name == model_name))
    if model is None:
        log.warning("no pricing for model, skipping accounting", extra={"model_name": model_name})
        return None

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cost_micros = compute_cost_micros(
        prompt_tokens, completion_tokens, model.input_cost_per_mtok, model.output_cost_per_mtok
    )

    record = RequestRecord(
        tenant_id=tenant_id,
        model_id=model.id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_micros=cost_micros,
    )
    session.add(record)
    await _upsert_usage_daily(
        session, tenant_id, model.id, prompt_tokens, completion_tokens, cost_micros
    )
    await session.commit()
    return record


async def _upsert_usage_daily(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    model_id: uuid.UUID,
    prompt_tokens: int,
    completion_tokens: int,
    cost_micros: int,
) -> None:
    today = datetime.now(UTC).date()
    stmt = pg_insert(UsageDaily).values(
        tenant_id=tenant_id,
        day=today,
        model_id=model_id,
        requests=1,
        tokens_in=prompt_tokens,
        tokens_out=completion_tokens,
        cost_micros=cost_micros,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["tenant_id", "day", "model_id"],
        set_={
            "requests": UsageDaily.requests + 1,
            "tokens_in": UsageDaily.tokens_in + prompt_tokens,
            "tokens_out": UsageDaily.tokens_out + completion_tokens,
            "cost_micros": UsageDaily.cost_micros + cost_micros,
        },
    )
    await session.execute(stmt)