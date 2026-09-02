import httpx
from fastapi import APIRouter, HTTPException

from switchboard.api.deps import CurrentTenantDep, ProviderDep

router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
async def chat_completions(
    payload: dict,
    tenant: CurrentTenantDep,
    provider: ProviderDep,
) -> dict:
    try:
        return await provider.chat_completion(payload)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.json(),
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="upstream request timed out",
        ) from exc