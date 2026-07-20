from typing import Annotated, cast

from fastapi import Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from credits_service.core.errors import CreditsError
from credits_service.services.identity import Identity, IdentityServiceProtocol

bearer = HTTPBearer(bearerFormat="JWT", scheme_name="AuthServiceJWT", auto_error=False)


def get_identity(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)]
) -> Identity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise CreditsError(401, "AUTHENTICATION_REQUIRED", "A valid bearer token is required")
    return cast(IdentityServiceProtocol, request.app.state.identity).verify(credentials.credentials)


def require_owner(identity: Annotated[Identity, Security(get_identity)]) -> Identity:
    if not identity.is_owner:
        raise CreditsError(403, "OWNER_REQUIRED", "Only an account owner can trade credits")
    return identity
