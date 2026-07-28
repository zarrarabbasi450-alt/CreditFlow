from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from conftest import FakeDatabase, FakeIdentityService
from tenant_service.core.config import Settings, get_settings
from tenant_service.main import create_app
from tenant_service.models import TENANT_SCHEMA, Account, AccountMember, Base, Invite
from tenant_service.schemas.accounts import AccountCreate
from tenant_service.schemas.events import AccountEvent, AccountEventType
from tenant_service.services.accounts import AccountService
from tenant_service.services.rabbitmq import InMemoryEventBus


class SQLiteConnection(Protocol):
    def execute(self, statement: str) -> object: ...


class SQLiteDatabase:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def test_health_version_and_openapi(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/version").json() == {"service": "tenant-service", "version": "0.1.0"}
    assert client.get("/docs").status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    document = openapi.json()
    assert document["components"]["securitySchemes"]["AuthServiceJWT"] == {
        "type": "http",
        "description": "RS256 access token issued by the CreditFlow Auth Service",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    assert document["paths"]["/api/v1/accounts/my"]["get"]["security"] == [{"AuthServiceJWT": []}]


def test_ready_success_and_failure(client: TestClient, database: FakeDatabase) -> None:
    assert client.get("/ready").json() == {
        "status": "ready",
        "checks": {"postgresql": "healthy"},
    }
    database.ping.side_effect = ConnectionError
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"postgresql": "unhealthy"}


def test_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PORT", "9002")
    monkeypatch.setenv("DATABASE_SCHEMA", "tenant")
    settings = Settings()
    assert settings.app_port == 9002
    assert settings.database_schema == "tenant"
    assert settings.database_url.endswith("/creditflow")


def test_account_model_validation() -> None:
    assert Base.metadata.schema == TENANT_SCHEMA
    assert set(Base.metadata.tables) == {
        "tenant.accounts",
        "tenant.account_members",
        "tenant.invites",
        "tenant.processed_events",
    }
    columns = Account.__table__.c
    assert columns.id.primary_key
    assert not columns.name.nullable
    assert not columns.slug.nullable and columns.slug.unique
    assert not columns.status.nullable and columns.status.server_default is not None
    assert columns.status.default is not None and columns.status.default.arg == "active"
    assert not columns.created_at.nullable and not columns.updated_at.nullable
    members = AccountMember.__table__.c
    assert not members.account_id.nullable and not members.user_id.nullable
    assert next(iter(members.account_id.foreign_keys)).target_fullname == "tenant.accounts.id"
    assert Invite.__table__.c.token_hash.unique


def test_migration_has_single_head() -> None:
    root = Path(__file__).parents[2]
    scripts = ScriptDirectory.from_config(Config(str(root / "alembic.ini")))
    assert scripts.get_current_head() == "0004_processed_events"


def test_account_event_schema() -> None:
    event = AccountEvent(
        event_type=AccountEventType.CREATED,
        account_id=uuid4(),
        data={"name": "Orion"},
    )
    assert event.event_type == "account.created" and event.data == {"name": "Orion"}


def test_application_shutdown(client: TestClient, database: FakeDatabase) -> None:
    assert client.get("/health").status_code == 200
    assert not database.close.called


@pytest.mark.asyncio
async def test_internal_owner_and_summary_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine.sync_engine, "connect")
    def attach_tenant(dbapi_connection: object, _connection_record: object) -> None:
        cast(SQLiteConnection, dbapi_connection).execute("ATTACH DATABASE ':memory:' AS tenant")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    service = AccountService(sessions, InMemoryEventBus())
    owner_id = uuid4()
    account = await service.create(AccountCreate(name="Internal", slug="internal", type="team"), owner_id)

    monkeypatch.setenv("TRUSTED_HOSTS", "localhost,127.0.0.1,testserver")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "shared-secret")
    get_settings.cache_clear()
    app = create_app(
        database=SQLiteDatabase(sessions), rabbitmq=InMemoryEventBus(), identity=FakeIdentityService()
    )
    with TestClient(app) as client:
        unauthorized = client.get(
            f"/api/v1/accounts/internal/{account.id}/owner",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert unauthorized.status_code == 401

        owner_response = client.get(
            f"/api/v1/accounts/internal/{account.id}/owner",
            headers={"Authorization": "Bearer shared-secret"},
        )
        assert owner_response.status_code == 200
        assert owner_response.json() == {"user_id": str(owner_id)}

        missing_owner = client.get(
            f"/api/v1/accounts/internal/{uuid4()}/owner",
            headers={"Authorization": "Bearer shared-secret"},
        )
        assert missing_owner.status_code == 404

        summary_response = client.get(
            f"/api/v1/accounts/internal/{account.id}/summary",
            headers={"Authorization": "Bearer shared-secret"},
        )
        assert summary_response.status_code == 200
        assert summary_response.json() == {
            "account_id": str(account.id),
            "plan_tier": "free",
            "seat_count": 1,
            "member_count": 1,
        }

        missing_summary = client.get(
            f"/api/v1/accounts/internal/{uuid4()}/summary",
            headers={"Authorization": "Bearer shared-secret"},
        )
        assert missing_summary.status_code == 404
    get_settings.cache_clear()
    await engine.dispose()
