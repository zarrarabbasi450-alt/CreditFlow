from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from admin_service.core.config import Settings
from admin_service.main import create_app
from admin_service.models import Base
from admin_service.schemas.admin import AccountSummary, ServiceHealthItem, SessionItem
from admin_service.services.directory import DirectoryClientProtocol
from admin_service.services.health import HealthCheckerProtocol
from admin_service.services.identity import Identity
from admin_service.services.rabbitmq import InMemoryEventBus
from admin_service.services.redis import InMemorySessionDirectory

SUPERADMIN_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_ACCOUNT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT_USER_ID = UUID("33333333-3333-3333-3333-333333333333")
OTHER_ACCOUNT_ID = UUID("44444444-4444-4444-4444-444444444444")


class TestIdentityService:
    def verify(self, token: str) -> Identity:
        if token == "superadmin":  # noqa: S105
            return Identity(SUPERADMIN_USER_ID, SUPERADMIN_USER_ID, "Owner", "SuperAdmin")
        return Identity(TENANT_USER_ID, TENANT_ACCOUNT_ID, "Owner")


class TestDatabase:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class FakeDirectoryClient(DirectoryClientProtocol):
    def __init__(self) -> None:
        self.summaries: dict[UUID, AccountSummary] = {
            TENANT_ACCOUNT_ID: AccountSummary(
                account_id=TENANT_ACCOUNT_ID,
                plan_tier="pro",
                seat_count=5,
                member_count=3,
                credit_balance=1000,
                usage_tokens=200,
                usage_quota_tokens=1_000_000,
            )
        }

    async def get_account_summary(self, account_id: UUID) -> AccountSummary:
        return self.summaries.get(
            account_id,
            AccountSummary(
                account_id=account_id,
                plan_tier=None,
                seat_count=None,
                member_count=None,
                credit_balance=None,
                usage_tokens=None,
                usage_quota_tokens=None,
            ),
        )

    async def close(self) -> None:
        return None


class FakeHealthChecker(HealthCheckerProtocol):
    async def check_all(self) -> list[ServiceHealthItem]:
        return [
            ServiceHealthItem(
                service="auth-service", status="Healthy", uptime=100.0, latencyP95Ms=12, detail="OK"
            )
        ]

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def app(tmp_path: Path) -> AsyncIterator[Any]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}",
        execution_options={"schema_translate_map": {"admin": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    database = TestDatabase(sessions)
    events = InMemoryEventBus()
    session_directory = InMemorySessionDirectory()
    directory = FakeDirectoryClient()
    health = FakeHealthChecker()
    settings = Settings(internal_service_token="internal-test-token")  # noqa: S106
    application = create_app(
        database=database,
        events=events,
        session_directory=session_directory,
        directory=directory,
        health=health,
        identity_service=TestIdentityService(),
    )
    application.state.settings = settings
    from admin_service.services.admin import AdminService

    admin = AdminService(sessions, session_directory, directory, health)
    application.state.admin = admin
    await events.start(admin.consume)
    yield application
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def superadmin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer superadmin"}


@pytest.fixture
def tenant_headers() -> dict[str, str]:
    return {"Authorization": "Bearer tenant"}


async def seed_session(directory: InMemorySessionDirectory, jti: str, session_item: SessionItem) -> None:
    directory.sessions[jti] = session_item
