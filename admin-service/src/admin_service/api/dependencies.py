from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from admin_service.core.errors import AdminError
from admin_service.services.admin import AdminService
from admin_service.services.identity import Identity, IdentityServiceProtocol

bearer = HTTPBearer(auto_error=False)


def get_admin_service(request: Request) -> AdminService:
    service = getattr(request.app.state, "admin", None)
    if not isinstance(service, AdminService):
        raise AdminError(503, "ADMIN_SERVICE_UNAVAILABLE", "Admin Service is not ready")
    return service


def get_identity_service(request: Request) -> IdentityServiceProtocol:
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise AdminError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable")
    return cast(IdentityServiceProtocol, service)


async def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    identity_service: Annotated[IdentityServiceProtocol, Depends(get_identity_service)],
) -> Identity:
    if credentials is None:
        raise AdminError(401, "AUTH_REQUIRED", "Bearer token is required")
    return identity_service.verify(credentials.credentials)
