from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from scraper_service.core.errors import ScraperError
from scraper_service.services.identity import Identity, IdentityServiceProtocol
from scraper_service.services.scraper import ScraperService

bearer = HTTPBearer(auto_error=False)


def get_scraper_service(request: Request) -> ScraperService:
    service = getattr(request.app.state, "scraper", None)
    if not isinstance(service, ScraperService):
        raise ScraperError(503, "SCRAPER_SERVICE_UNAVAILABLE", "Scraper Service is not ready")
    return service


def get_identity_service(request: Request) -> IdentityServiceProtocol:
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise ScraperError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable")
    return cast(IdentityServiceProtocol, service)


async def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    identity_service: Annotated[IdentityServiceProtocol, Depends(get_identity_service)],
) -> Identity:
    if credentials is None:
        raise ScraperError(401, "AUTH_REQUIRED", "Bearer token is required")
    return identity_service.verify(credentials.credentials)
