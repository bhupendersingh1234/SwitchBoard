from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from switchboard.auth.tenancy import AuthenticationError, authenticate
from switchboard.core.resources import Resources
from switchboard.db.models import Tenant
from switchboard.providers.base import Provider
from switchboard.limits.rate_limit import RateLimitExceeded, enforce_rpm_limit

def get_resources(request: Request) -> Resources:
    resources: Resources | None = getattr(request.app.state, "resources", None)
    if resources is None:
        raise RuntimeError("application resources are not initialised")
    return resources


ResourcesDep = Annotated[Resources, Depends(get_resources)]


def get_provider(resources: ResourcesDep) -> Provider:
    return resources.provider


ProviderDep = Annotated[Provider, Depends(get_provider)]


async def get_session(resources: ResourcesDep) -> AsyncIterator[AsyncSession]:
    async with resources.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_tenant(
    session: SessionDep,
    authorization: str | None = Header(default=None),
) -> Tenant:
    try:
        return await authenticate(session, authorization)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


CurrentTenantDep = Annotated[Tenant, Depends(get_current_tenant)]


async def check_rate_limit(tenant: CurrentTenantDep, resources: ResourcesDep) -> None:
    try:
        await enforce_rpm_limit(resources.rate_limiter, tenant.id, resources.settings.rpm_limit)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


RateLimitDep = Annotated[None, Depends(check_rate_limit)]