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
from switchboard.resilience.breaker import CircuitOpenError
from switchboard.resilience.timeouts import DeadlineExceeded, with_deadline

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

_PROVIDER_ERRORS = (
    httpx.HTTPStatusError,
    httpx.TimeoutException,
    httpx.ConnectError,
    CircuitOpenError,
    DeadlineExceeded,
)


def _classify_provider_error(
    exc: Exception, recovery_timeout: float
) -> tuple[int, object, dict[str, str]]:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code, exc.response.json(), {}
    if isinstance(exc, DeadlineExceeded):
        return 504, "request deadline exceeded", {}
    if isinstance(exc, httpx.TimeoutException):
        return 504, "upstream request timed out", {}
    if isinstance(exc, httpx.ConnectError):
        return 502, "could not reach upstream provider", {}
    return (
        503,
        "upstream provider is temporarily unavailable",
        {"Retry-After": str(int(recovery_timeout))},
    )


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
        response = await with_deadline(
            lambda: provider.chat_completion(payload),
            deadline_s=resources.settings.request_deadline_s,
        )
    except _PROVIDER_ERRORS as exc:
        await refund_tpm_budget(
            resources.rate_limiter, tenant.id, resources.settings.tpm_limit, estimated_tokens
        )
        status_code, detail, headers = _classify_provider_error(
            exc, resources.settings.provider_recovery_timeout
        )
        raise HTTPException(status_code=status_code, detail=detail, headers=headers) from exc

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