from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from notification_service.core.config import Settings
from notification_service.main import create_app
from notification_service.models import Base
from notification_service.services.directory import DirectoryClientProtocol
from notification_service.services.email import EmailClientProtocol, EmailSendResult
from notification_service.services.identity import Identity
from notification_service.services.notifications import NotificationService
from notification_service.services.rabbitmq import InMemoryEventBus
from notification_service.services.slack import SlackClientProtocol

TEST_ACCOUNT_ID = UUID("22222222-2222-2222-2222-222222222222")
TEST_USER_ID = UUID("11111111-1111-1111-1111-111111111111")


class TestIdentityService:
    def verify(self, token: str) -> Identity:
        del token
        return Identity(user_id=TEST_USER_ID, account_id=TEST_ACCOUNT_ID, account_role="Owner")


class TestDatabase:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class FakeEmailClient(EmailClientProtocol):
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str, str]] = []

    async def send(self, to: str, subject: str, html: str, text: str) -> EmailSendResult:
        self.sent.append((to, subject, html, text))
        return EmailSendResult(provider_message_id="test-message-id")

    async def close(self) -> None:
        return None


class FakeSlackClient(SlackClientProtocol):
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, text: str) -> None:
        self.sent.append(text)

    async def close(self) -> None:
        return None


class FakeDirectoryClient(DirectoryClientProtocol):
    def __init__(self) -> None:
        self.users: dict[UUID, str] = {TEST_USER_ID: "owner@example.com"}
        self.account_owners: dict[UUID, UUID] = {TEST_ACCOUNT_ID: TEST_USER_ID}

    async def get_user_email(self, user_id: UUID) -> str | None:
        return self.users.get(user_id)

    async def get_account_owner_email(self, account_id: UUID) -> str | None:
        owner = self.account_owners.get(account_id)
        return self.users.get(owner) if owner else None

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def app(tmp_path: Path) -> AsyncIterator[Any]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'notifications.db'}",
        execution_options={"schema_translate_map": {"notifications": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    database = TestDatabase(sessions)
    events = InMemoryEventBus()
    email = FakeEmailClient()
    slack = FakeSlackClient()
    directory = FakeDirectoryClient()
    settings = Settings(internal_service_token="internal-test-token")  # noqa: S106
    application = create_app(
        database=database,
        events=events,
        email=email,
        slack=slack,
        directory=directory,
        identity_service=TestIdentityService(),
    )
    application.state.settings = settings
    notifications = NotificationService(sessions, events, email, slack, directory, settings.frontend_url)
    application.state.notifications = notifications
    await events.start(notifications.consume)
    yield application
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test"}
