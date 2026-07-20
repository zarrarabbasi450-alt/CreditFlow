import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_service.core.errors import AuthError
from auth_service.models import EmailVerificationToken, User
from auth_service.services.rabbitmq import EventPublisherProtocol


class EmailVerificationService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        publisher: EventPublisherProtocol,
        expiry_hours: int,
    ) -> None:
        self.sessions = sessions
        self.publisher = publisher
        self.expiry_hours = expiry_hours

    async def create(self, user_id: UUID, email: str) -> None:
        raw_token = secrets.token_urlsafe(32)
        async with self.sessions() as session, session.begin():
            session.add(
                EmailVerificationToken(
                    user_id=user_id,
                    token_hash=self.hash_token(raw_token),
                    expires_at=datetime.now(UTC) + timedelta(hours=self.expiry_hours),
                )
            )
        await self.publisher.publish(
            "user.registered",
            {"user_id": str(user_id), "email": email, "verification_token": raw_token},
        )

    async def verify(self, raw_token: str) -> None:
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            stored = await session.scalar(
                select(EmailVerificationToken)
                .where(EmailVerificationToken.token_hash == self.hash_token(raw_token))
                .with_for_update()
            )
            if stored is None or stored.used_at is not None:
                raise AuthError(400, "INVALID_VERIFICATION_TOKEN", "Verification token is invalid")
            expires_at = (
                stored.expires_at.replace(tzinfo=UTC)
                if stored.expires_at.tzinfo is None
                else stored.expires_at
            )
            if expires_at <= now:
                raise AuthError(400, "VERIFICATION_TOKEN_EXPIRED", "Verification token has expired")
            user = await session.get(User, stored.user_id)
            if user is None:
                raise AuthError(400, "INVALID_VERIFICATION_TOKEN", "Verification token is invalid")
            stored.used_at = now
            user.is_email_verified = True

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
