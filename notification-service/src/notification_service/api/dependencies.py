from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from notification_service.core.errors import NotificationError
from notification_service.services.identity import Identity, IdentityServiceProtocol
from notification_service.services.notifications import NotificationService

bearer = HTTPBearer(auto_error=False)


def get_notification_service(request: Request) -> NotificationService:
    service = getattr(request.app.state, "notifications", None)
    if not isinstance(service, NotificationService):
        raise NotificationError(503, "NOTIFICATION_SERVICE_UNAVAILABLE", "Notification Service is not ready")
    return service


def get_identity_service(request: Request) -> IdentityServiceProtocol:
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise NotificationError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable")
    return cast(IdentityServiceProtocol, service)


async def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    identity_service: Annotated[IdentityServiceProtocol, Depends(get_identity_service)],
) -> Identity:
    if credentials is None:
        raise NotificationError(401, "AUTH_REQUIRED", "Bearer token is required")
    return identity_service.verify(credentials.credentials)
