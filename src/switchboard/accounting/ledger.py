import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from switchboard.accounting.pricing import compute_cost_micros
from switchboard.db.models import Model, RequestRecord

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
    await session.commit()
    return record