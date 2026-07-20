from typing import Annotated, cast

from fastapi import Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tenant_service.core.errors import TenantError
from tenant_service.services.identity import Identity, IdentityServiceProtocol

bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    scheme_name="AuthServiceJWT",
    description="RS256 access token issued by the CreditFlow Auth Service",
    auto_error=False,
)


async def get_actor(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)] = None,
) -> Identity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise TenantError(401, "AUTHENTICATION_REQUIRED", "A valid bearer token is required")
    identity = cast(IdentityServiceProtocol, request.app.state.identity)
    return identity.verify(credentials.credentials)
