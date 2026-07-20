from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient

from conftest import FakeDatabase
from tenant_service.core.config import Settings
from tenant_service.models import TENANT_SCHEMA, Account, AccountMember, Base, Invite
from tenant_service.schemas.events import AccountEvent, AccountEventType


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
    assert scripts.get_current_head() == "0003_invites"


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
