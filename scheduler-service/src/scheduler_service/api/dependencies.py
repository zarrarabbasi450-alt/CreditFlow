from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from scheduler_service.core.errors import SchedulerError
from scheduler_service.services.identity import Identity, IdentityServiceProtocol
from scheduler_service.services.scheduler import SchedulerService

bearer = HTTPBearer(auto_error=False)


def get_scheduler_service(request: Request) -> SchedulerService:
    service = getattr(request.app.state, "scheduler", None)
    if not isinstance(service, SchedulerService):
        raise SchedulerError(503, "SCHEDULER_SERVICE_UNAVAILABLE", "Scheduler Service is not ready")
    return service


def get_identity_service(request: Request) -> IdentityServiceProtocol:
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise SchedulerError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable")
    return cast(IdentityServiceProtocol, service)


async def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    identity_service: Annotated[IdentityServiceProtocol, Depends(get_identity_service)],
) -> Identity:
    if credentials is None:
        raise SchedulerError(401, "AUTH_REQUIRED", "Bearer token is required")
    return identity_service.verify(credentials.credentials)
