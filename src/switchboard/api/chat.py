import httpx
from fastapi import APIRouter, HTTPException

from switchboard.api.deps import ResourcesDep

router = APIRouter(tags=["chat"])


@router.post("/v1/chat/completions")
async def chat_completions(payload: dict, resources: ResourcesDep) -> dict:
    try:
        return await resources.provider.chat_completion(payload)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.json()
        ) from exc