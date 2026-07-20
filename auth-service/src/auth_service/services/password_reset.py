import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_service.core.errors import AuthError
from auth_service.models import Credential, PasswordResetToken, RefreshToken, User
from auth_service.services.rabbitmq import EventPublisherProtocol
from auth_service.services.redis import RedisProtocol


class PasswordResetService:
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
        raw_token = secrets.token_urlsafe(32)
        user: User | None
        async with self.sessions() as session, session.begin():
            user = await session.scalar(
                select(User).where(func.lower(User.email) == normalized, User.is_active.is_(True))
            )
            if user is not None:
                session.add(
                    PasswordResetToken(
                        user_id=user.id,
                        token_hash=self.hash_token(raw_token),
                        expires_at=datetime.now(UTC) + timedelta(minutes=self.expiry_minutes),
                    )
                )
        if user is not None:
            await self.publisher.publish(
                "user.password_reset_requested",
                {"user_id": str(user.id), "email": user.email, "reset_token": raw_token},
            )

    async def reset(self, raw_token: str, password: str) -> None:
        now = datetime.now(UTC)
        user_id = None
        async with self.sessions() as session, session.begin():
            stored = await session.scalar(
                select(PasswordResetToken)
                .where(PasswordResetToken.token_hash == self.hash_token(raw_token))
                .with_for_update()
            )
            if stored is None or stored.used_at is not None:
                raise AuthError(400, "INVALID_RESET_TOKEN", "Password reset token is invalid")
            expires_at = (
                stored.expires_at.replace(tzinfo=UTC)
                if stored.expires_at.tzinfo is None
                else stored.expires_at
            )
            if expires_at <= now:
                raise AuthError(400, "RESET_TOKEN_EXPIRED", "Password reset token has expired")
            credential = await session.scalar(
                select(Credential).where(Credential.user_id == stored.user_id).with_for_update()
            )
            if credential is None:
                raise AuthError(400, "INVALID_RESET_TOKEN", "Password reset token is invalid")
            credential.password_hash = self.passwords.hash(password)
            credential.password_changed_at = now
            stored.used_at = now
            user_id = stored.user_id
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == stored.user_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=now)
            )
        if user_id is not None:
            await self.redis.revoke_user_sessions(user_id)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
