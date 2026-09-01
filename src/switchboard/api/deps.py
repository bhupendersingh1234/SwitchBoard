from typing import Annotated

from fastapi import Depends, Request

from switchboard.core.resources import Resources
from switchboard.providers.base import Provider


def get_resources(request: Request) -> Resources:
    resources: Resources | None = getattr(request.app.state, "resources", None)
    if resources is None:
        raise RuntimeError("application resources are not initialised")
    return resources


ResourcesDep = Annotated[Resources, Depends(get_resources)]


def get_provider(resources: ResourcesDep) -> Provider:
    return resources.provider


ProviderDep = Annotated[Provider, Depends(get_provider)]