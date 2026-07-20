from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth_service.core.config import Settings
from auth_service.models import AUTH_SCHEMA, Base, Credential, PasswordResetToken, RefreshToken, User
from auth_service.services.auth import AuthIdentity, AuthResult
from auth_service.services.jwt import TokenPair
from conftest import FakeDatabase


def test_health_version_and_openapi(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/version").json() == {"service": "auth-service", "version": "0.1.0"}
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_request_context(client: TestClient) -> None:
    response = client.get(
        "/health", headers={"X-Request-ID": "request-1", "X-Correlation-ID": "correlation-1"}
    )
    assert response.headers["x-request-id"] == "request-1"
    assert response.headers["x-correlation-id"] == "correlation-1"


def test_ready_success_and_failure(client: TestClient, database: FakeDatabase) -> None:
    assert client.get("/ready").status_code == 200
    database.ping.side_effect = ConnectionError
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"postgresql": "unhealthy"}


def test_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_PORT", "9001")
    monkeypatch.setenv("DATABASE_SCHEMA", "auth")
    settings = Settings()
    assert settings.app_port == 9001
    assert settings.database_schema == "auth"
    assert settings.database_url.endswith("/creditflow")


def test_database_models() -> None:
    assert Base.metadata.schema == AUTH_SCHEMA
    assert set(Base.metadata.tables) == {
        "auth.users",
        "auth.credentials",
        "auth.refresh_tokens",
        "auth.password_reset_tokens",
        "auth.email_verification_tokens",
    }
    assert User.__table__.c.email.unique
    assert Credential.__table__.c.user_id.unique
    assert RefreshToken.__table__.c.jti.unique
    assert PasswordResetToken.__table__.c.token_hash.unique
    assert next(iter(Credential.__table__.c.user_id.foreign_keys)).target_fullname == "auth.users.id"


def test_migration_has_single_head() -> None:
    root = Path(__file__).parents[2]
    config = Config(str(root / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_current_head() == "0003_platform_role"
    assert scripts.get_revision("0001_auth_schema") is not None


def test_application_shutdown(client: TestClient, database: FakeDatabase) -> None:
    assert client.get("/health").status_code == 200
    assert not database.close.called


def test_authentication_routes(client: TestClient) -> None:
    identity = AuthIdentity(uuid4(), "owner@example.com", uuid4(), "Owner")
    tokens = TokenPair(
        "access", "refresh", 900, "access-jti", datetime.now(UTC), "refresh-jti", datetime.now(UTC)
    )
    authentication = AsyncMock()
    authentication.signup.return_value = identity
    authentication.login.return_value = AuthResult(identity, tokens)
    authentication.refresh.return_value = AuthResult(identity, tokens)
    cast(FastAPI, client.app).state.authentication = authentication

    signup = client.post("/api/v1/auth/signup", json={"email": identity.email, "password": "Password123!"})
    assert signup.status_code == 201 and signup.json()["data"]["role"] == "Owner"
    login = client.post("/api/v1/auth/login", json={"email": identity.email, "password": "Password123!"})
    assert login.status_code == 200 and login.json()["data"]["tokens"]["accessToken"] == "access"
    refresh = client.post("/api/v1/auth/refresh", json={"refreshToken": "refresh"})
    assert refresh.status_code == 200 and refresh.json()["data"]["tokens"]["refreshToken"] == "refresh"
    invalid = client.post("/api/v1/auth/signup", json={"email": "bad", "password": "short"})
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "VALIDATION_ERROR"
