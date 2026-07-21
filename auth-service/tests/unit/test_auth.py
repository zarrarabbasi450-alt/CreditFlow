from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from auth_service.core.config import Settings
from auth_service.core.errors import AuthError
from auth_service.models import Base, Credential, RefreshToken, User
from auth_service.services.auth import AuthService
from auth_service.services.email_verification import EmailVerificationService
from auth_service.services.jwt import JWTService
from auth_service.services.password_reset import PasswordResetService
from auth_service.services.rabbitmq import InMemoryEventPublisher
from auth_service.services.redis import InMemoryRedisService


class SQLiteConnection(Protocol):
    def execute(self, statement: str) -> object: ...


def write_keys(directory: Path) -> tuple[Path, Path]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = directory / "private.pem"
    public_path = directory / "public.pem"
    private_path.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return private_path, public_path


@pytest.fixture
async def authentication(tmp_path: Path) -> AsyncIterator[AuthService]:
    private_path, public_path = write_keys(tmp_path)
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine.sync_engine, "connect")
    def attach_auth(dbapi_connection: object, _connection_record: object) -> None:
        cast(SQLiteConnection, dbapi_connection).execute("ATTACH DATABASE ':memory:' AS auth")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    settings = Settings(
        jwt_private_key_path=str(private_path),
        jwt_public_key_path=str(public_path),
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
    )
    redis = InMemoryRedisService()
    publisher = InMemoryEventPublisher()
    yield AuthService(
        sessions, JWTService(settings), redis, EmailVerificationService(sessions, publisher, 24), 5, 900
    )
    await engine.dispose()


@pytest.mark.asyncio
async def test_signup_login_and_refresh_rotation(authentication: AuthService) -> None:
    identity = await authentication.signup("OWNER@EXAMPLE.COM", "Password123!")
    assert identity.email == "owner@example.com"
    assert identity.account_id == identity.user_id and identity.role == "Owner"

    with pytest.raises(AuthError) as duplicate:
        await authentication.signup("owner@example.com", "Password123!")
    assert duplicate.value.code == "EMAIL_ALREADY_REGISTERED"

    with pytest.raises(AuthError) as invalid:
        await authentication.login("owner@example.com", "wrong-password", "127.0.0.1")
    assert invalid.value.code == "INVALID_CREDENTIALS"

    login = await authentication.login("owner@example.com", "Password123!", "127.0.0.1")
    publisher = cast(InMemoryEventPublisher, authentication.verification.publisher)
    assert publisher.events[-1][0] == "user.logged_in"
    assert publisher.events[-1][1]["user_id"] == str(identity.user_id)
    current = await authentication.current_identity(login.tokens.access_token)
    assert current.user_id == identity.user_id
    with pytest.raises(AuthError) as forbidden:
        await authentication.require_superadmin(login.tokens.access_token)
    assert forbidden.value.code == "SUPERADMIN_REQUIRED"
    claims = authentication.tokens.decode_refresh(login.tokens.refresh_token)
    assert claims["user_id"] == str(identity.user_id)
    assert claims["account_id"] == str(identity.account_id)
    assert claims["role"] == "Owner"

    rotated = await authentication.refresh(login.tokens.refresh_token)
    assert rotated.tokens.refresh_token != login.tokens.refresh_token
    with pytest.raises(AuthError) as reused:
        await authentication.refresh(login.tokens.refresh_token)
    assert reused.value.code == "INVALID_REFRESH_TOKEN"

    async with authentication.sessions() as session:
        stored = list((await session.scalars(select(RefreshToken))).all())
    assert len(stored) == 2
    assert stored[0].revoked_at is not None
    assert stored[0].replaced_by_jti == stored[1].jti


@pytest.mark.asyncio
async def test_verification_reset_rate_limit_and_logout(authentication: AuthService) -> None:
    identity = await authentication.signup("security@example.com", "Password123!")
    publisher = cast(InMemoryEventPublisher, authentication.verification.publisher)
    registered = publisher.events[-1]
    assert registered[0] == "user.registered"
    verification_token = cast(str, registered[1]["verification_token"])
    await authentication.verification.verify(verification_token)

    for _ in range(5):
        with pytest.raises(AuthError):
            await authentication.login("security@example.com", "Wrong123!", "10.0.0.1")
    with pytest.raises(AuthError) as limited:
        await authentication.login("security@example.com", "Wrong123!", "10.0.0.1")
    assert limited.value.status_code == 429

    login = await authentication.login("security@example.com", "Password123!", "10.0.0.1")
    await authentication.logout(login.tokens.access_token, login.tokens.refresh_token)
    async with authentication.sessions() as session:
        refresh = await session.scalar(select(RefreshToken).where(RefreshToken.user_id == identity.user_id))
    assert refresh is not None and refresh.revoked_at is not None

    reset = PasswordResetService(authentication.sessions, authentication.redis, publisher, 30)
    await reset.request(identity.email)
    reset_event = publisher.events[-1]
    assert reset_event[0] == "user.password_reset_requested"
    await reset.reset(cast(str, reset_event[1]["reset_token"]), "NewPassword123!")
    relogin = await authentication.login(identity.email, "NewPassword123!", "10.0.0.3")
    assert relogin.identity.user_id == identity.user_id

    async with authentication.sessions() as session:
        user = await session.get(User, identity.user_id)
        credential = await session.scalar(select(Credential).where(Credential.user_id == identity.user_id))
    assert user is not None and user.is_email_verified
    assert credential is not None and credential.password_changed_at is not None


@pytest.mark.asyncio
async def test_last_superadmin_cannot_be_removed(authentication: AuthService) -> None:
    identity = await authentication.signup("root@example.com", "Password123!")
    async with authentication.sessions() as session, session.begin():
        user = await session.get(User, identity.user_id)
        assert user is not None
        user.platform_role = "SuperAdmin"
    with pytest.raises(AuthError) as caught:
        await authentication.update_platform_role(identity.user_id, None)
    assert caught.value.code == "LAST_SUPERADMIN_REQUIRED"


def test_jwt_configuration_error() -> None:
    service = JWTService(Settings(jwt_private_key_path="", jwt_public_key_path=""))
    with pytest.raises(AuthError) as caught:
        service.issue_pair(uuid4(), uuid4(), "Owner", "owner@example.com")
    assert caught.value.code == "JWT_CONFIGURATION_ERROR"
