from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from scheduler_service.main import create_app
from scheduler_service.models import Base
from scheduler_service.services.identity import Identity
from scheduler_service.services.rabbitmq import InMemoryEventBus
from scheduler_service.services.redis_lock import InMemoryLockService
from scheduler_service.services.scheduler import SchedulerService


class TestIdentityService:
    def verify(self, token: str) -> Identity:
        del token
        return Identity(
            user_id=UUID("11111111-1111-1111-1111-111111111111"),
            account_id=UUID("22222222-2222-2222-2222-222222222222"),
            account_role="Owner",
        )


class TestDatabase:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def app(tmp_path: Path) -> AsyncIterator[Any]:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'scheduler.db'}",
        execution_options={"schema_translate_map": {"scheduler": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    database = TestDatabase(sessions)
    events = InMemoryEventBus()
    locks = InMemoryLockService()
    service = SchedulerService(sessions, events, locks)
    application = create_app(
        database=database, events=events, locks=locks, identity_service=TestIdentityService()
    )
    application.state.scheduler = service
    yield application
    await engine.dispose()


@pytest_asyncio.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test"}
