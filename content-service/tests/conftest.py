from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from content_service.core.config import Settings
from content_service.main import create_app
from content_service.models import Base
from content_service.services.content import ContentService
from content_service.services.identity import Identity
from content_service.services.rabbitmq import InMemoryEventBus
from content_service.services.storage import LocalStorage

ACCOUNT_ID = uuid4()
OTHER_ACCOUNT_ID = uuid4()
USER_ID = uuid4()


class IdentityStub:
    def verify(self, token: str) -> Identity:
        normalized = token.casefold()
        if normalized.startswith("member"):
            return Identity(USER_ID, ACCOUNT_ID, "Member")
        if normalized.startswith("other"):
            return Identity(USER_ID, OTHER_ACCOUNT_ID, "Owner")
        if normalized.startswith("super"):
            return Identity(USER_ID, OTHER_ACCOUNT_ID, "Member", "SuperAdmin")
        return Identity(USER_ID, ACCOUNT_ID, "Owner")


class DatabaseStub:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


@pytest.fixture
async def context(tmp_path: Path) -> AsyncIterator[dict[str, Any]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"content": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    events = InMemoryEventBus()
    storage = LocalStorage(str(tmp_path / "uploads"), "http://testserver/uploads")
    database = DatabaseStub(sessions)
    content = ContentService(sessions, events)
    app = create_app(database, events, storage, IdentityStub())
    app.state.settings = Settings(_env_file=None)
    app.state.database = database
    app.state.events = events
    app.state.storage = storage
    app.state.content = content
    app.state.identity_service = IdentityStub()
    await events.start(content.consume)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield {"client": client, "events": events, "sessions": sessions}
    await engine.dispose()


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": "Bearer owner"}
