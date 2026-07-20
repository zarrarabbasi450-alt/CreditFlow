from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID, uuid4

import jwt

from auth_service.core.config import Settings
from auth_service.core.errors import AuthError


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    access_jti: str
    access_expires_at: datetime
    refresh_jti: str
    refresh_expires_at: datetime


class JWTService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def issue_pair(
        self,
        user_id: UUID,
        account_id: UUID,
        account_role: str,
        email: str,
        platform_role: str | None = None,
    ) -> TokenPair:
        now = datetime.now(UTC)
        access_expires = now + timedelta(minutes=self.settings.access_token_expire_minutes)
        refresh_expires = now + timedelta(days=self.settings.refresh_token_expire_days)
        access_jti = str(uuid4())
        access = self._encode(
            user_id,
            account_id,
            account_role,
            email,
            platform_role,
            "access",
            access_jti,
            now,
            access_expires,
        )
        refresh_jti = str(uuid4())
        refresh = self._encode(
            user_id,
            account_id,
            account_role,
            email,
            platform_role,
            "refresh",
            refresh_jti,
            now,
            refresh_expires,
        )
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            access_expires_in=self.settings.access_token_expire_minutes * 60,
            access_jti=access_jti,
            access_expires_at=access_expires,
            refresh_jti=refresh_jti,
            refresh_expires_at=refresh_expires,
        )

    def decode_refresh(self, token: str) -> dict[str, Any]:
        return self._decode(token, "refresh")

    def decode_access(self, token: str) -> dict[str, Any]:
        return self._decode(token, "access")

    def _decode(self, token: str, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._read_key(self.settings.jwt_public_key_path, "public"),
                algorithms=["RS256"],
                issuer=self.settings.jwt_issuer,
                audience=self.settings.jwt_audience,
                options={
                    "require": [
                        "sub",
                        "user_id",
                        "account_id",
                        "role",
                        "account_role",
                        "jti",
                        "iat",
                        "exp",
                        "token_type",
                    ]
                },
            )
            if payload.get("token_type") != expected_type:
                raise AuthError(401, "INVALID_TOKEN", "Token is invalid")
            return cast(dict[str, Any], payload)
        except jwt.ExpiredSignatureError as exc:
            raise AuthError(401, "TOKEN_EXPIRED", "Token has expired") from exc
        except jwt.PyJWTError as exc:
            raise AuthError(401, "INVALID_TOKEN", "Token is invalid") from exc

    def _encode(
        self,
        user_id: UUID,
        account_id: UUID,
        account_role: str,
        email: str,
        platform_role: str | None,
        token_type: Literal["access", "refresh"],
        jti: str,
        issued_at: datetime,
        expires_at: datetime,
    ) -> str:
        payload = {
            "sub": str(user_id),
            "user_id": str(user_id),
            "account_id": str(account_id),
            "role": platform_role or account_role,
            "account_role": account_role,
            "platform_role": platform_role,
            "email": email,
            "jti": jti,
            "iat": issued_at,
            "exp": expires_at,
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "token_type": token_type,
        }
        return jwt.encode(
            payload,
            self._read_key(self.settings.jwt_private_key_path, "private"),
            algorithm="RS256",
        )

    @staticmethod
    def _read_key(path_value: str, kind: str) -> str:
        if not path_value:
            raise AuthError(503, "JWT_CONFIGURATION_ERROR", f"JWT {kind} key path is not configured")
        path = Path(path_value).expanduser()
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise AuthError(503, "JWT_CONFIGURATION_ERROR", f"JWT {kind} key is unavailable") from exc
