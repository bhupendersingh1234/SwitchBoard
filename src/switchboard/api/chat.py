import logging

import httpx
from fastapi import APIRouter, HTTPException

from switchboard.accounting.ledger import record_usage
from switchboard.api.deps import (
    BudgetDep,
    CurrentTenantDep,
    EstimatedTokensDep,
    ProviderDep,
    RateLimitDep,
    ResourcesDep,
    SessionDep,
)
from switchboard.limits.rate_limit import refund_tpm_budget

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
async def chat_completions(
    payload: dict,
    tenant: CurrentTenantDep,
    _budget: BudgetDep,
    _rate_limit: RateLimitDep,
    estimated_tokens: EstimatedTokensDep,
    provider: ProviderDep,
    session: SessionDep,
    resources: ResourcesDep,
) -> dict:
    try:
        response = await provider.chat_completion(payload)
    except httpx.HTTPStatusError as exc:
        await refund_tpm_budget(
            resources.rate_limiter, tenant.id, resources.settings.tpm_limit, estimated_tokens
        )
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.json()
        ) from exc
    except httpx.TimeoutException as exc:
        await refund_tpm_budget(
            resources.rate_limiter, tenant.id, resources.settings.tpm_limit, estimated_tokens
        )
        raise HTTPException(status_code=504, detail="upstream request timed out") from exc

    usage = response.get("usage", {})
    actual_tokens = usage.get("total_tokens", estimated_tokens)
    if estimated_tokens > actual_tokens:
        await refund_tpm_budget(
            resources.rate_limiter,
            tenant.id,
            resources.settings.tpm_limit,
            estimated_tokens - actual_tokens,
        )

    try:
        await record_usage(session, tenant.id, payload.get("model", ""), usage)
    except Exception:
        log.exception("failed to record usage")

    return response