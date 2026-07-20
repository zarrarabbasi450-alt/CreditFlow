from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from api_gateway.core.config import get_settings
from api_gateway.main import create_app

PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC = (
    PRIVATE.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)


def make_token(**overrides: Any) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": "user-1",
        "user_id": "user-1",
        "jti": "session-1",
        "role": "Owner",
        "account_id": "account-1",
        "account_role": "Owner",
        "token_type": "access",
        "iss": "creditflow-auth",
        "aud": "creditflow-api",
        "exp": now + timedelta(minutes=5),
        **overrides,
    }
    return jwt.encode(payload, PRIVATE, algorithm="RS256")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("ALLOW_IN_MEMORY_REDIS", "true")
    monkeypatch.setenv("JWT_PUBLIC_KEY", PUBLIC)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("LINKEDIN_WEBHOOK_SECRET", "linkedin-secret")
    monkeypatch.setenv("OPENROUTER_WEBHOOK_SECRET", "openrouter-secret")
    get_settings.cache_clear()
    with TestClient(create_app()) as value:
        value.app.state.redis.events["auth:session:session-1"] = (
            datetime.now(UTC) + timedelta(minutes=5)
        ).timestamp()
        yield value
    get_settings.cache_clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}
