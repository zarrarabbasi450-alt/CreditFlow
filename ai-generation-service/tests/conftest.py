from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from ai_generation_service.core.config import Settings
from ai_generation_service.main import create_app
from ai_generation_service.models import Base
from ai_generation_service.services.identity import Identity
from ai_generation_service.services.openrouter import InMemoryAIProvider
from ai_generation_service.services.rabbitmq import InMemoryEventBus
from ai_generation_service.services.redis import InMemoryRedisService
from ai_generation_service.services.usage import InMemoryUsageClient

ACCOUNT_ID = uuid4()
USER_ID = uuid4()


class IdentityStub:
    def verify(self, token: str) -> Identity:
        if token.casefold().startswith("super"):
            return Identity(USER_ID, ACCOUNT_ID, "Member", "SuperAdmin")
        return Identity(USER_ID, ACCOUNT_ID, "Owner")


class DatabaseStub:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


@pytest.fixture
async def context() -> AsyncIterator[dict[str, Any]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"ai_generation": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    redis = InMemoryRedisService()
    events = InMemoryEventBus()
    usage = InMemoryUsageClient()
    ai = InMemoryAIProvider(["Hello", " from", " CreditFlow"])
    settings = Settings(_env_file=None)
    app = create_app(DatabaseStub(sessions), redis, events, usage, ai, identity=IdentityStub())
    app.state.settings = settings
    app.state.generations.settings = settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield {"client": client, "app": app, "redis": redis, "events": events, "usage": usage}
    await engine.dispose()


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": "Bearer owner"}
