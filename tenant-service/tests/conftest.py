from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from tenant_service.core.config import get_settings
from tenant_service.main import create_app
from tenant_service.models import MemberRole
from tenant_service.services.identity import Identity
from tenant_service.services.rabbitmq import InMemoryEventBus


class FakeIdentityService:
    def __init__(self) -> None:
        from uuid import uuid4

        self.identity = Identity(uuid4(), uuid4(), MemberRole.OWNER)

    def verify(self, token: str) -> Identity:
        del token
        return self.identity


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
    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")
    get_settings.cache_clear()
    with TestClient(
        create_app(
            database=database,
            rabbitmq=InMemoryEventBus(),
            identity=FakeIdentityService(),
        )
    ) as value:
        yield value
    get_settings.cache_clear()
