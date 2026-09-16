import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from switchboard.db.models import CascadeDecision


async def record_cascade_decision(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    messages: list[dict],
    response_content: str,
    tier_model: str,
    was_low_quality: bool,
) -> None:
    """Record one cascade tier's decision for later fine-tuning export.

    Storing raw conversation content is a real privacy decision, not a
    default - the caller (chat.py) only calls this when
    settings.collect_finetuning_data is explicitly enabled. This function
    itself does not check that flag; it just does what it's told, so the
    opt-in decision lives in exactly one place rather than being re-checked
    (and possibly re-implemented inconsistently) here too.
    """
    session.add(
        CascadeDecision(
            tenant_id=tenant_id,
            messages=messages,
            response_content=response_content,
            tier_model=tier_model,
            was_low_quality=was_low_quality,
        )
    )
    await session.commit()