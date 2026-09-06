import logging

import httpx
from fastapi import APIRouter, HTTPException

from switchboard.accounting.ledger import record_usage
from switchboard.api.deps import CurrentTenantDep, ProviderDep, SessionDep, RateLimitDep

log = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
async def chat_completions(
    payload: dict, tenant: CurrentTenantDep, _rate_limit: RateLimitDep, provider: ProviderDep, session: SessionDep
) -> dict:
    try:
        response = await provider.chat_completion(payload)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.json()
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="upstream request timed out") from exc

    try:
        await record_usage(session, tenant.id, payload.get("model", ""), response.get("usage", {}))
    except Exception:
        log.exception("failed to record usage")

    return response