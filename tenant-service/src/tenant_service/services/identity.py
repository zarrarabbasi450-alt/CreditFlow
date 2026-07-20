from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import jwt

from tenant_service.core.config import Settings
from tenant_service.core.errors import TenantError
from tenant_service.models import MemberRole


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    account_id: UUID
    role: MemberRole
    platform_role: str | None = None

    @property
    def is_superadmin(self) -> bool:
        return self.platform_role == "SuperAdmin"


class IdentityServiceProtocol(Protocol):
    def verify(self, token: str) -> Identity: ...


class JWTIdentityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify(self, token: str) -> Identity:
        key = self.settings.jwt_public_key.replace("\\n", "\n")
        if not key and self.settings.jwt_public_key_path:
            try:
                key = Path(self.settings.jwt_public_key_path).expanduser().read_text(encoding="utf-8")
            except OSError as exc:
                raise TenantError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable") from exc
        if not key:
            raise TenantError(503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable")
        try:
            payload = cast(
                dict[str, Any],
                jwt.decode(
                    token,
                    key,
                    algorithms=["RS256"],
                    issuer=self.settings.jwt_issuer,
                    audience=self.settings.jwt_audience,
                    options={
                        "require": [
                            "user_id",
                            "account_id",
                            "role",
                            "account_role",
                            "token_type",
                            "exp",
                        ]
                    },
                ),
            )
            if payload["token_type"] != "access":  # noqa: S105 - JWT token category, not a password
                raise TenantError(401, "INVALID_TOKEN", "Access token is invalid")
            return Identity(
                user_id=UUID(str(payload["user_id"])),
                account_id=UUID(str(payload["account_id"])),
                role=MemberRole(str(payload["account_role"]).lower()),
                platform_role=(
                    str(payload["platform_role"]) if payload.get("platform_role") is not None else None
                ),
            )
        except jwt.ExpiredSignatureError as exc:
            raise TenantError(401, "TOKEN_EXPIRED", "Access token has expired") from exc
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise TenantError(401, "INVALID_TOKEN", "Access token is invalid") from exc
