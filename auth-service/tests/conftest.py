from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import get_settings
from auth_service.main import create_app
from auth_service.services.rabbitmq import InMemoryEventPublisher
from auth_service.services.redis import InMemoryRedisService


class FakeDatabase:
    def __init__(self) -> None:
        self.sessions = AsyncMock()
        self.ping = AsyncMock(return_value=True)
        self.close = AsyncMock()


@pytest.fixture
def database() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, database: FakeDatabase) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:test@localhost:5432/creditflow")
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")
    get_settings.cache_clear()
    with TestClient(
        create_app(database=database, redis=InMemoryRedisService(), publisher=InMemoryEventPublisher())
    ) as value:
        yield value
    get_settings.cache_clear()
