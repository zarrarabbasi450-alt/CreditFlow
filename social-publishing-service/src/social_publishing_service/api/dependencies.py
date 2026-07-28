from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from social_publishing_service.core.errors import SocialPublishingError
from social_publishing_service.services.identity import Identity, IdentityServiceProtocol
from social_publishing_service.services.publishing import SocialPublishingService

bearer = HTTPBearer(auto_error=False)


def get_publishing_service(request: Request) -> SocialPublishingService:
    service = getattr(request.app.state, "publishing", None)
    if not isinstance(service, SocialPublishingService):
        raise SocialPublishingError(
            503, "SOCIAL_PUBLISHING_UNAVAILABLE", "Social Publishing Service is not ready"
        )
    return service


def get_identity_service(request: Request) -> IdentityServiceProtocol:
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise SocialPublishingError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable")
    return cast(IdentityServiceProtocol, service)


async def get_credentials(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> HTTPAuthorizationCredentials:
    if credentials is None:
        raise SocialPublishingError(401, "AUTH_REQUIRED", "Bearer token is required")
    return credentials


async def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(get_credentials)],
    identity_service: Annotated[IdentityServiceProtocol, Depends(get_identity_service)],
) -> Identity:
    return identity_service.verify(credentials.credentials)
