import asyncio
import logging

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

from switchboard.core.resources import Resources
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

log = logging.getLogger(__name__)
router = APIRouter(tags=["ops"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def _check_db(resources: Resources) -> None:
    async with resources.engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _check_redis(resources: Resources) -> None:
    await resources.redis.ping()


@router.get("/readyz")
async def readyz(request: Request, response: Response) -> dict[str, object]:
    resources: Resources | None = getattr(request.app.state, "resources", None)
    if resources is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "starting", "checks": {}}

    checks = {"postgres": _check_db(resources), "redis": _check_redis(resources)}
    timeout = resources.settings.readiness_timeout_s
    results: dict[str, str] = {}

    async def run(name: str, coro: object) -> None:
        try:
            async with asyncio.timeout(timeout):
                await coro  # type: ignore[misc]
        except TimeoutError:
            results[name] = "timeout"
            log.warning("readiness check timed out", extra={"dependency": name})
        except Exception as exc:
            results[name] = "error"
            log.warning("readiness check failed", extra={"dependency": name, "error": str(exc)})
        else:
            results[name] = "ok"

    await asyncio.gather(*(run(name, coro) for name, coro in checks.items()))

    healthy = all(v == "ok" for v in results.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": results}


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)