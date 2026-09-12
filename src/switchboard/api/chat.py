import json
import logging
import time
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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


async def _stream_chat_completions(
    payload: dict,
    tenant: CurrentTenantDep,
    estimated_tokens: int,
    provider: ProviderDep,
    resources: ResourcesDep,
) -> StreamingResponse:
    stream = provider.stream_chat_completion(payload)
    start = time.monotonic()

    try:
        first_chunk = await with_deadline(
            lambda: anext(stream), deadline_s=resources.settings.request_deadline_s
        )
    except StopAsyncIteration:
        first_chunk = None
    except _PROVIDER_ERRORS as exc:
        await refund_tpm_budget(
            resources.rate_limiter, tenant.id, resources.settings.tpm_limit, estimated_tokens
        )
        status_code, detail, headers = _classify_provider_error(
            exc, resources.settings.provider_recovery_timeout
        )
        raise HTTPException(status_code=status_code, detail=detail, headers=headers) from exc

    ttft_ms = int((time.monotonic() - start) * 1000)
    log.info("stream ttft", extra={"ttft_ms": ttft_ms, "tenant_id": str(tenant.id)})

    async def event_generator() -> AsyncIterator[bytes]:
        if first_chunk is not None:
            yield f"data: {json.dumps(first_chunk)}\n\n".encode()
        try:
            async for chunk in stream:
                yield f"data: {json.dumps(chunk)}\n\n".encode()
        except _PROVIDER_ERRORS:
            # A byte is already on the wire. We can't retry or change the status
            # code now - the only honest thing left to do is stop and log it.
            log.exception("stream failed after first chunk, ending early")
        finally:
            yield b"data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    payload: dict,
    tenant: CurrentTenantDep,
    _budget: BudgetDep,
    _rate_limit: RateLimitDep,
    estimated_tokens: EstimatedTokensDep,
    provider: ProviderDep,
    session: SessionDep,
    resources: ResourcesDep,
) -> dict | StreamingResponse:
    if payload.get("stream"):
        return await _stream_chat_completions(payload, tenant, estimated_tokens, provider, resources)

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