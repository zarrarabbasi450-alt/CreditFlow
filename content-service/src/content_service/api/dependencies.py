from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from content_service.core.errors import ContentError
from content_service.services.content import ContentService
from content_service.services.identity import Identity, IdentityServiceProtocol
from content_service.services.storage import LocalStorage

bearer = HTTPBearer(auto_error=False)


def get_content_service(request: Request) -> ContentService:
    service = getattr(request.app.state, "content", None)
    if not isinstance(service, ContentService):
        raise ContentError(503, "CONTENT_SERVICE_UNAVAILABLE", "Content Service is not ready")
    return service


def get_storage(request: Request) -> LocalStorage:
    storage = getattr(request.app.state, "storage", None)
    if not isinstance(storage, LocalStorage):
        raise ContentError(503, "STORAGE_UNAVAILABLE", "Upload storage is not ready")
    return storage


def get_identity_service(request: Request) -> IdentityServiceProtocol:
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise ContentError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable")
    return cast(IdentityServiceProtocol, service)


async def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    identity_service: Annotated[IdentityServiceProtocol, Depends(get_identity_service)],
) -> Identity:
    if credentials is None:
        raise ContentError(401, "AUTH_REQUIRED", "Bearer token is required")
    return identity_service.verify(credentials.credentials)
