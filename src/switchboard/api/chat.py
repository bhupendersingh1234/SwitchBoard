import json
import logging
import time
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from opentelemetry import trace

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
from switchboard.cache.exact import get_cached_response, set_cached_response
from switchboard.cache.keys import compute_cache_key, is_cacheable
from switchboard.limits.rate_limit import refund_tpm_budget
from switchboard.observability.metrics import (
    CACHE_HITS_TOTAL,
    CACHE_MISSES_TOTAL,
    CASCADE_ESCALATIONS_TOTAL,
    CASCADE_REQUESTS_TOTAL,
    TTFT_SECONDS,
)
from switchboard.resilience.breaker import CircuitOpenError
from switchboard.resilience.timeouts import DeadlineExceeded, with_deadline
from switchboard.routing.cascade import CascadeLeg

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
    payload = {**payload, "stream_options": {"include_usage": True}}
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

    ttft_s = time.monotonic() - start
    TTFT_SECONDS.observe(ttft_s)
    log.info("stream ttft", extra={"ttft_ms": int(ttft_s * 1000), "tenant_id": str(tenant.id)})

    model_name = payload.get("model", "")

    async def event_generator() -> AsyncIterator[bytes]:
        usage: dict = {}
        try:
            if first_chunk is not None:
                if first_chunk.get("usage"):
                    usage = first_chunk["usage"]
                yield f"data: {json.dumps(first_chunk)}\n\n".encode()
            async for chunk in stream:
                if chunk.get("usage"):
                    usage = chunk["usage"]
                yield f"data: {json.dumps(chunk)}\n\n".encode()
            yield b"data: [DONE]\n\n"
        except _PROVIDER_ERRORS:
            # A byte is already on the wire. We can't retry or change the status
            # code now - the only honest thing left to do is stop and log it.
            log.exception("stream failed after first chunk, ending early")
            yield b"data: [DONE]\n\n"
        finally:
            # Closing the outer generator does NOT automatically close the inner
            # provider stream it's iterating - I verified this directly. Without
            # this explicit close, the inner generator (and the real HTTP
            # connection to the upstream inside it) would only get cleaned up
            # eventually, whenever garbage collection happens to finalize it -
            # not deterministically, and not what "cancels the upstream call"
            # actually requires.
            try:
                await stream.aclose()
            except Exception:
                log.exception("failed to close upstream stream cleanly")

            if usage:
                remaining = estimated_tokens - usage.get("total_tokens", estimated_tokens)
                if remaining > 0:
                    await refund_tpm_budget(
                        resources.rate_limiter, tenant.id, resources.settings.tpm_limit, remaining
                    )
                try:
                    async with resources.sessionmaker() as cleanup_session:
                        await record_usage(cleanup_session, tenant.id, model_name, usage)
                except Exception:
                    log.exception("failed to record usage for stream")
            else:
                log.warning(
                    "stream ended before usage was known, no cost recorded",
                    extra={"tenant_id": str(tenant.id)},
                )

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
    cache_control: str | None = Header(default=None),
) -> dict | StreamingResponse:
    if payload.get("stream"):
        return await _stream_chat_completions(
            payload, tenant, estimated_tokens, provider, resources
        )

    bypass_cache = cache_control is not None and "no-store" in cache_control
    cache_key = None
    if is_cacheable(payload) and not bypass_cache:
        cache_key = compute_cache_key(tenant.id, payload)
        cached = await get_cached_response(resources.redis, cache_key)
        if cached is not None:
            CACHE_HITS_TOTAL.inc()
        else:
            CACHE_MISSES_TOTAL.inc()
        log.info(
            "cache lookup",
            extra={
                "cache_result": "hit" if cached is not None else "miss",
                "tenant_id": str(tenant.id),
            },
        )
        if cached is not None:
            await refund_tpm_budget(
                resources.rate_limiter, tenant.id, resources.settings.tpm_limit, estimated_tokens
            )
            return cached

    is_cascade = payload.get("model") == resources.settings.cascade_model_name
    if is_cascade:
        CASCADE_REQUESTS_TOTAL.inc()

    try:
        if is_cascade:
            response, legs = await with_deadline(
                lambda: resources.cascade_provider.chat_completion_with_legs(payload),
                deadline_s=resources.settings.request_deadline_s,
            )
        else:
            response = await with_deadline(
                lambda: provider.chat_completion(payload),
                deadline_s=resources.settings.request_deadline_s,
            )
            legs = [CascadeLeg(model=payload.get("model", ""), usage=response.get("usage", {}))]
    except _PROVIDER_ERRORS as exc:
        await refund_tpm_budget(
            resources.rate_limiter, tenant.id, resources.settings.tpm_limit, estimated_tokens
        )
        status_code, detail, headers = _classify_provider_error(
            exc, resources.settings.provider_recovery_timeout
        )
        raise HTTPException(status_code=status_code, detail=detail, headers=headers) from exc

    if len(legs) > 1:
        CASCADE_ESCALATIONS_TOTAL.inc()
        trace.get_current_span().set_attribute("sb.cascade_escalated", True)
        log.info(
            "cascade escalated",
            extra={
                "tenant_id": str(tenant.id),
                "cheap_model": legs[0].model,
                "expensive_model": legs[-1].model,
            },
        )

    actual_tokens = sum(leg.usage.get("total_tokens", 0) for leg in legs)
    if estimated_tokens > actual_tokens:
        await refund_tpm_budget(
            resources.rate_limiter,
            tenant.id,
            resources.settings.tpm_limit,
            estimated_tokens - actual_tokens,
        )

    if cache_key is not None:
        await set_cached_response(
            resources.redis, cache_key, response, ttl_s=resources.settings.cache_ttl_s
        )

    for leg in legs:
        try:
            await record_usage(session, tenant.id, leg.model, leg.usage)
        except Exception:
            log.exception("failed to record usage", extra={"model": leg.model})

    return response