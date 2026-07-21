import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auth_service.core.errors import AuthError
from auth_service.models import Credential, RefreshToken, User
from auth_service.services.email_verification import EmailVerificationService
from auth_service.services.jwt import JWTService, TokenPair
from auth_service.services.redis import RedisProtocol


@dataclass(frozen=True)
class AuthIdentity:
    user_id: UUID
    email: str
    account_id: UUID
    account_role: str
    platform_role: str | None = None

    @property
    def role(self) -> str:
        return self.platform_role or self.account_role


def is_owner(identity: AuthIdentity) -> bool:
    return identity.account_role == "Owner" or is_superadmin(identity)


def is_admin(identity: AuthIdentity) -> bool:
    return identity.account_role in {"Owner", "Admin"} or is_superadmin(identity)


def is_member(identity: AuthIdentity) -> bool:
    return identity.account_role in {"Owner", "Admin", "Member"} or is_superadmin(identity)


def is_superadmin(identity: AuthIdentity) -> bool:
    return identity.platform_role == "SuperAdmin"


@dataclass(frozen=True)
class AuthResult:
    identity: AuthIdentity
    tokens: TokenPair


class AuthService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        tokens: JWTService,
        redis: RedisProtocol,
        verification: EmailVerificationService,
        login_limit: int,
        login_window: int,
        bootstrap_superadmin_email: str = "",
        tenant_service_url: str = "http://localhost:8002",
    ) -> None:
        self.sessions = sessions
        self.tokens = tokens
        self.passwords = PasswordHasher()
        self.redis = redis
        self.verification = verification
        self.login_limit = login_limit
        self.login_window = login_window
        self.bootstrap_superadmin_email = bootstrap_superadmin_email.strip().lower()
        self.tenant_service_url = tenant_service_url.rstrip("/")

    async def signup(self, email: str, password: str) -> AuthIdentity:
        normalized = email.strip().lower()
        user = User(
            email=normalized,
            platform_role="SuperAdmin" if normalized == self.bootstrap_superadmin_email else None,
        )
        try:
            async with self.sessions() as session, session.begin():
                existing = await session.scalar(select(User.id).where(func.lower(User.email) == normalized))
                if existing is not None:
                    raise AuthError(
                        409, "EMAIL_ALREADY_REGISTERED", "An account with this email already exists"
                    )
                session.add(user)
                await session.flush()
                session.add(Credential(user_id=user.id, password_hash=self.passwords.hash(password)))
        except IntegrityError as exc:
            raise AuthError(
                409, "EMAIL_ALREADY_REGISTERED", "An account with this email already exists"
            ) from exc
        identity = self._identity(user)
        await self.verification.create(identity.user_id, identity.email)
        return identity

    async def login(self, email: str, password: str, ip: str) -> AuthResult:
        normalized = email.strip().lower()
        async with self.sessions() as session, session.begin():
            row = (
                await session.execute(
                    select(User, Credential)
                    .join(Credential, Credential.user_id == User.id)
                    .where(func.lower(User.email) == normalized)
                )
            ).one_or_none()
            if (
                row is None
                or not row.User.is_active
                or not self._verify(row.Credential.password_hash, password)
            ):
                if not await self.redis.login_allowed(normalized, ip, self.login_limit):
                    raise AuthError(429, "LOGIN_RATE_LIMITED", "Too many failed login attempts")
                await self.redis.record_login_failure(normalized, ip, self.login_window)
                raise AuthError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")
            identity = self._identity(row.User)
            pair = self.tokens.issue_pair(
                identity.user_id,
                identity.account_id,
                identity.account_role,
                identity.email,
                identity.platform_role,
            )
            session.add(self._refresh_record(identity.user_id, pair))
        await self.redis.clear_login_failures(normalized, ip)
        await self._store_access(identity, pair)
        await self.verification.publisher.publish(
            "user.logged_in",
            {
                "user_id": str(identity.user_id),
                "account_id": str(identity.account_id),
                "role": identity.role,
                "jti": pair.access_jti,
            },
        )
        return AuthResult(identity, pair)

    async def refresh(self, raw_token: str) -> AuthResult:
        claims = self.tokens.decode_refresh(raw_token)
        token_hash = self.hash_token(raw_token)
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            stored = await session.scalar(
                select(RefreshToken)
                .where(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.jti == str(claims["jti"]),
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
                .with_for_update()
            )
            if stored is None:
                raise AuthError(401, "INVALID_REFRESH_TOKEN", "Refresh token is invalid or already used")
            user = await session.scalar(
                select(User).where(User.id == stored.user_id, User.is_active.is_(True))
            )
            if user is None:
                raise AuthError(401, "INVALID_REFRESH_TOKEN", "Refresh token is invalid")
            identity = AuthIdentity(
                user.id,
                user.email,
                UUID(str(claims["account_id"])),
                str(claims["account_role"]),
                user.platform_role,
            )
            pair = self.tokens.issue_pair(
                identity.user_id,
                identity.account_id,
                identity.account_role,
                identity.email,
                identity.platform_role,
            )
            stored.revoked_at = now
            stored.replaced_by_jti = pair.refresh_jti
            session.add(self._refresh_record(identity.user_id, pair))
        await self._store_access(identity, pair)
        return AuthResult(identity, pair)

    async def switch_account(self, access_token: str, account_id: UUID) -> AuthResult:
        claims = self.tokens.decode_access(access_token)
        user_id = UUID(str(claims["user_id"]))
        if not await self.redis.session_active(str(claims["jti"])):
            raise AuthError(401, "SESSION_REVOKED", "Access token session is no longer active")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.tenant_service_url}/api/v1/accounts/{account_id}/membership/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.HTTPError as exc:
            raise AuthError(503, "TENANT_SERVICE_UNAVAILABLE", "Tenant Service is unavailable") from exc
        if response.status_code == 404:
            raise AuthError(403, "ACCOUNT_ACCESS_DENIED", "You do not belong to this account")
        if response.status_code >= 400:
            raise AuthError(502, "TENANT_SERVICE_ERROR", "Tenant Service rejected the account switch")
        account_role = str(response.json().get("role", "")).title()
        if account_role not in {"Owner", "Admin", "Member"}:
            raise AuthError(502, "INVALID_ACCOUNT_ROLE", "Tenant Service returned an invalid account role")
        async with self.sessions() as session, session.begin():
            user = await session.get(User, user_id)
            if user is None or not user.is_active:
                raise AuthError(401, "INVALID_TOKEN", "User is not active")
            identity = AuthIdentity(user.id, user.email, account_id, account_role, user.platform_role)
            pair = self.tokens.issue_pair(
                identity.user_id,
                identity.account_id,
                identity.account_role,
                identity.email,
                identity.platform_role,
            )
            session.add(self._refresh_record(identity.user_id, pair))
        await self.redis.revoke_session(str(claims["jti"]), user_id)
        await self._store_access(identity, pair)
        return AuthResult(identity, pair)

    async def logout(self, access_token: str, refresh_token: str) -> None:
        access_claims = self.tokens.decode_access(access_token)
        refresh_claims = self.tokens.decode_refresh(refresh_token)
        if access_claims["user_id"] != refresh_claims["user_id"]:
            raise AuthError(401, "INVALID_TOKEN", "Tokens do not belong to the same session")
        now = datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            stored = await session.scalar(
                select(RefreshToken).where(
                    RefreshToken.token_hash == self.hash_token(refresh_token),
                    RefreshToken.jti == str(refresh_claims["jti"]),
                )
            )
            if stored is not None and stored.revoked_at is None:
                stored.revoked_at = now
        await self.redis.revoke_session(str(access_claims["jti"]), UUID(str(access_claims["user_id"])))

    async def _store_access(self, identity: AuthIdentity, pair: TokenPair) -> None:
        ttl = max(int((pair.access_expires_at - datetime.now(UTC)).total_seconds()), 1)
        await self.redis.store_session(
            pair.access_jti,
            identity.user_id,
            identity.account_id,
            identity.account_role,
            identity.platform_role,
            ttl,
        )

    async def require_superadmin(self, access_token: str) -> AuthIdentity:
        identity = await self.current_identity(access_token)
        if not is_superadmin(identity):
            raise AuthError(403, "SUPERADMIN_REQUIRED", "SuperAdmin access is required")
        return identity

    async def current_identity(self, access_token: str) -> AuthIdentity:
        claims = self.tokens.decode_access(access_token)
        if not await self.redis.session_active(str(claims["jti"])):
            raise AuthError(401, "SESSION_REVOKED", "Access token session is no longer active")
        async with self.sessions() as session:
            user = await session.get(User, UUID(str(claims["user_id"])))
            if user is None or not user.is_active:
                raise AuthError(401, "INVALID_TOKEN", "User is not active")
            return AuthIdentity(
                user.id,
                user.email,
                UUID(str(claims["account_id"])),
                str(claims["account_role"]),
                user.platform_role,
            )

    async def list_users(self) -> list[User]:
        async with self.sessions() as session:
            return list((await session.scalars(select(User).order_by(User.created_at))).all())

    async def update_platform_role(self, user_id: UUID, platform_role: str | None) -> User:
        async with self.sessions() as session, session.begin():
            user = await session.get(User, user_id)
            if user is None:
                raise AuthError(404, "USER_NOT_FOUND", "User was not found")
            if user.platform_role == "SuperAdmin" and platform_role is None:
                remaining = await session.scalar(
                    select(func.count(User.id)).where(
                        User.platform_role == "SuperAdmin",
                        User.is_active.is_(True),
                    )
                )
                if int(remaining or 0) <= 1:
                    raise AuthError(
                        409,
                        "LAST_SUPERADMIN_REQUIRED",
                        "The final active SuperAdmin cannot be removed",
                    )
            user.platform_role = platform_role
        await self.redis.revoke_user_sessions(user_id)
        return user

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _refresh_record(self, user_id: UUID, pair: TokenPair) -> RefreshToken:
        return RefreshToken(
            user_id=user_id,
            token_hash=self.hash_token(pair.refresh_token),
            jti=pair.refresh_jti,
            expires_at=pair.refresh_expires_at,
        )

    def _verify(self, password_hash: str, password: str) -> bool:
        try:
            return self.passwords.verify(password_hash, password)
        except VerifyMismatchError, VerificationError, InvalidHashError:
            return False

    @staticmethod
    def _identity(user: User) -> AuthIdentity:
        return AuthIdentity(user.id, user.email, user.id, "Owner", user.platform_role)
