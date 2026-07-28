import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

import jwt

from notification_service.core.config import Settings
from notification_service.core.errors import NotificationError

INTERNAL_SERVICE_ID = UUID(int=0)


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    account_id: UUID
    account_role: str
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
        if self.settings.internal_service_token and secrets.compare_digest(
            token, self.settings.internal_service_token
        ):
            return Identity(INTERNAL_SERVICE_ID, INTERNAL_SERVICE_ID, "Owner", "SuperAdmin")
        key = self.settings.jwt_public_key.replace("\\n", "\n")
        if not key and self.settings.jwt_public_key_path:
            try:
                key = Path(self.settings.jwt_public_key_path).read_text(encoding="utf-8")
            except OSError as exc:
                raise NotificationError(
                    503, "AUTH_CONFIGURATION_ERROR", "JWT verification is unavailable"
                ) from exc
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
                            "jti",
                            "token_type",
                            "exp",
                        ]
                    },
                ),
            )
            if payload["token_type"] != "access":  # noqa: S105
                raise NotificationError(401, "INVALID_TOKEN", "Access token is invalid")
            return Identity(
                UUID(str(payload["user_id"])),
                UUID(str(payload["account_id"])),
                str(payload["account_role"]),
                str(payload["platform_role"]) if payload.get("platform_role") else None,
            )
        except jwt.ExpiredSignatureError as exc:
            raise NotificationError(401, "TOKEN_EXPIRED", "Access token has expired") from exc
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise NotificationError(401, "INVALID_TOKEN", "Access token is invalid") from exc
