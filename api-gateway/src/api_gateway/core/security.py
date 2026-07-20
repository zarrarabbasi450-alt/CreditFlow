from pathlib import Path
from typing import Literal

import jwt
from pydantic import BaseModel

from api_gateway.core.config import Settings
from api_gateway.core.errors import GatewayError


class TokenClaims(BaseModel):
    sub: str
    user_id: str
    jti: str
    role: Literal["Owner", "Admin", "Member", "SuperAdmin"]
    account_id: str
    account_role: Literal["Owner", "Admin", "Member"]
    platform_role: Literal["SuperAdmin"] | None = None
    token_type: Literal["access"]
    iss: str
    aud: str | list[str]
    exp: int


def verify_access_token(token: str, settings: Settings) -> TokenClaims:
    public_key = settings.jwt_public_key.replace("\\n", "\n")
    if not public_key and settings.jwt_public_key_path:
        try:
            public_key = Path(settings.jwt_public_key_path).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise GatewayError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is not configured") from exc
    if not public_key:
        raise GatewayError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is not configured")
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={
                "require": [
                    "exp",
                    "iss",
                    "aud",
                    "sub",
                    "user_id",
                    "jti",
                    "role",
                    "account_id",
                    "account_role",
                    "token_type",
                ]
            },
        )
        return TokenClaims.model_validate(payload)
    except jwt.ExpiredSignatureError as exc:
        raise GatewayError(401, "TOKEN_EXPIRED", "Access token has expired") from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise GatewayError(401, "INVALID_TOKEN", "Access token is invalid") from exc


def is_owner(claims: TokenClaims) -> bool:
    return claims.account_role == "Owner" or is_superadmin(claims)


def is_admin(claims: TokenClaims) -> bool:
    return claims.account_role in {"Owner", "Admin"} or is_superadmin(claims)


def is_member(claims: TokenClaims) -> bool:
    return claims.account_role in {"Owner", "Admin", "Member"} or is_superadmin(claims)


def is_superadmin(claims: TokenClaims) -> bool:
    return claims.platform_role == "SuperAdmin"


def enforce_route_role(method: str, path: str, claims: TokenClaims) -> None:
    if path.startswith("/api/v1/admin") and not is_superadmin(claims):
        raise GatewayError(403, "SUPERADMIN_REQUIRED", "SuperAdmin access is required")
    credits_management = path.startswith("/api/v1/credits/marketplace") and method in {
        "POST",
        "PATCH",
        "DELETE",
    }
    if credits_management and not is_owner(claims):
        raise GatewayError(403, "OWNER_REQUIRED", "Account Owner access is required")
    if not path.startswith("/api/v1/billing"):
        return
    owner_only = (method == "GET" and path in {"/api/v1/billing/overview", "/api/v1/billing/invoices"}) or (
        method == "POST"
        and (
            path in {"/api/v1/billing/portal", "/api/v1/billing/refunds", "/api/v1/billing/escrows"}
            or path.startswith("/api/v1/billing/escrows/")
        )
    )
    manager = (
        (method == "POST" and path == "/api/v1/billing/checkout")
        or (method == "PATCH" and path == "/api/v1/billing/subscription")
        or (method == "GET" and path == "/api/v1/billing/subscription")
    )
    if owner_only and not is_owner(claims):
        raise GatewayError(403, "OWNER_REQUIRED", "Account Owner access is required")
    if manager and not is_owner(claims):
        raise GatewayError(403, "OWNER_REQUIRED", "Account Owner access is required")
