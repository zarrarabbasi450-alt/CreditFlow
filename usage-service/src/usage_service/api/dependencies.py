from typing import Annotated, cast

from fastapi import Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from usage_service.core.errors import UsageError
from usage_service.services.identity import Identity, IdentityServiceProtocol

bearer = HTTPBearer(bearerFormat="JWT", scheme_name="AuthServiceJWT", auto_error=False)


def get_identity(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)]
) -> Identity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UsageError(401, "AUTHENTICATION_REQUIRED", "A valid bearer token is required")
    verifier = cast(IdentityServiceProtocol, request.app.state.identity)
    return verifier.verify(credentials.credentials)
