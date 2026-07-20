from typing import Annotated, cast

from fastapi import Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from billing_service.core.errors import BillingError
from billing_service.services.identity import Identity, IdentityServiceProtocol

bearer = HTTPBearer(bearerFormat="JWT", scheme_name="AuthServiceJWT", auto_error=False)


def get_identity(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)]
) -> Identity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise BillingError(401, "AUTHENTICATION_REQUIRED", "A valid bearer token is required")
    verifier = cast(IdentityServiceProtocol, request.app.state.identity)
    return verifier.verify(credentials.credentials)


def require_owner(identity: Annotated[Identity, Security(get_identity)]) -> Identity:
    if identity.role.lower() != "owner" and not identity.is_superadmin:
        raise BillingError(403, "OWNER_REQUIRED", "Only an account owner can manage billing")
    return identity
