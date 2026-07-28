import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from argon2 import PasswordHasher
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_service.core.errors import AuthError
from auth_service.models import Credential, PasswordResetToken, RefreshToken, User
from auth_service.services.rabbitmq import EventPublisherProtocol
from auth_service.services.redis import RedisProtocol

OTP_ATTEMPT_LIMIT = 5
OTP_ATTEMPT_WINDOW_SECONDS = 900


class PasswordResetService:
    """One-time-code (OTP) password reset. A 6-digit code is emailed on request,
    checked (without consuming it) via `verify`, then consumed together with the
    new password via `reset`. Both `verify` and `reset` are rate-limited per
    email+IP since a 6-digit code is guessable if left unprotected."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        redis: RedisProtocol,
        publisher: EventPublisherProtocol,
        expiry_minutes: int,
    ) -> None:
        self.sessions = sessions
        self.redis = redis
        self.publisher = publisher
        self.expiry_minutes = expiry_minutes
        self.passwords = PasswordHasher()

    async def request(self, email: str) -> None:
        normalized = email.strip().lower()
        raw_code = f"{secrets.randbelow(1_000_000):06d}"
        user: User | None
        async with self.sessions() as session, session.begin():
            user = await session.scalar(
                select(User).where(func.lower(User.email) == normalized, User.is_active.is_(True))
            )
            if user is not None:
                session.add(
                    PasswordResetToken(
                        user_id=user.id,
                        token_hash=self.hash_token(raw_code),
                        expires_at=datetime.now(UTC) + timedelta(minutes=self.expiry_minutes),
                    )
                )
        if user is not None:
            await self.publisher.publish(
                "user.password_reset_requested",
                {"user_id": str(user.id), "email": user.email, "reset_code": raw_code},
            )

    async def verify(self, email: str, code: str, ip: str) -> None:
        normalized = email.strip().lower()
        if not await self.redis.otp_allowed(normalized, ip, OTP_ATTEMPT_LIMIT):
            raise AuthError(429, "TOO_MANY_ATTEMPTS", "Too many attempts — try again later")
        async with self.sessions() as session:
            user_id = await self._active_user_id(session, normalized)
            stored = await self._find_active(session, user_id, code) if user_id else None
        if stored is None:
            await self.redis.record_otp_failure(normalized, ip, OTP_ATTEMPT_WINDOW_SECONDS)
            raise AuthError(400, "INVALID_RESET_CODE", "Reset code is invalid or has expired")

    async def reset(self, email: str, code: str, password: str, ip: str) -> None:
        normalized = email.strip().lower()
        if not await self.redis.otp_allowed(normalized, ip, OTP_ATTEMPT_LIMIT):
            raise AuthError(429, "TOO_MANY_ATTEMPTS", "Too many attempts — try again later")
        now = datetime.now(UTC)
        user_id: UUID | None = None
        async with self.sessions() as session, session.begin():
            resolved_user_id = await self._active_user_id(session, normalized)
            stored = (
                await self._find_active(session, resolved_user_id, code, for_update=True)
                if resolved_user_id
                else None
            )
            if stored is None:
                await self.redis.record_otp_failure(normalized, ip, OTP_ATTEMPT_WINDOW_SECONDS)
                raise AuthError(400, "INVALID_RESET_CODE", "Reset code is invalid or has expired")
            credential = await session.scalar(
                select(Credential).where(Credential.user_id == stored.user_id).with_for_update()
            )
            if credential is None:
                raise AuthError(400, "INVALID_RESET_CODE", "Reset code is invalid or has expired")
            credential.password_hash = self.passwords.hash(password)
            credential.password_changed_at = now
            stored.used_at = now
            user_id = stored.user_id
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == stored.user_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )
        await self.redis.clear_otp_failures(normalized, ip)
        if user_id is not None:
            await self.redis.revoke_user_sessions(user_id)

    @staticmethod
    async def _active_user_id(session: AsyncSession, normalized_email: str) -> UUID | None:
        return cast(
            "UUID | None",
            await session.scalar(select(User.id).where(func.lower(User.email) == normalized_email)),
        )

    async def _find_active(
        self, session: AsyncSession, user_id: UUID, code: str, *, for_update: bool = False
    ) -> PasswordResetToken | None:
        now = datetime.now(UTC)
        statement = (
            select(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.token_hash == self.hash_token(code),
                PasswordResetToken.used_at.is_(None),
            )
            .order_by(PasswordResetToken.created_at.desc())
        )
        if for_update:
            statement = statement.with_for_update()
        stored = await session.scalar(statement)
        if stored is None:
            return None
        expires_at = (
            stored.expires_at.replace(tzinfo=UTC) if stored.expires_at.tzinfo is None else stored.expires_at
        )
        if expires_at <= now:
            return None
        return stored

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
