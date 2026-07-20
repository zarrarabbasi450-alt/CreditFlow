import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from api_gateway.core.config import Settings
from api_gateway.core.errors import GatewayError
from api_gateway.core.security import TokenClaims, enforce_route_role, verify_access_token
from api_gateway.schemas.events import EventEnvelope
from api_gateway.services.proxy import ProxyService
from api_gateway.services.rate_limiter import RateLimiter
from api_gateway.services.redis import InMemoryRedisService
from api_gateway.services.sse import SSEService
from conftest import PUBLIC, make_token


def test_liveness_version_and_docs(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/version").status_code == 200
    assert client.get("/docs").status_code == 200


def test_gateway_role_enforcement_and_superadmin_bypass() -> None:
    base = {
        "sub": "user-1",
        "user_id": "user-1",
        "jti": "session-1",
        "account_id": "account-1",
        "account_role": "Admin",
        "token_type": "access",
        "iss": "creditflow-auth",
        "aud": "creditflow-api",
        "exp": 2_000_000_000,
    }
    admin = TokenClaims.model_validate({**base, "role": "Admin"})
    with pytest.raises(GatewayError) as denied:
        enforce_route_role("GET", "/api/v1/billing/invoices", admin)
    assert denied.value.status_code == 403
    superadmin = TokenClaims.model_validate({**base, "role": "SuperAdmin", "platform_role": "SuperAdmin"})
    enforce_route_role("GET", "/api/v1/billing/invoices", superadmin)
    enforce_route_role("GET", "/api/v1/admin/users", superadmin)


def test_request_and_correlation_ids(client: TestClient) -> None:
    response = client.get(
        "/health", headers={"X-Request-ID": "request-1", "X-Correlation-ID": "correlation-1"}
    )
    assert response.headers["x-request-id"] == "request-1"
    assert response.headers["x-correlation-id"] == "correlation-1"


def test_readiness_success_and_failure(client: TestClient) -> None:
    client.app.state.rabbitmq.ping = AsyncMock(return_value=True)
    assert client.get("/ready").status_code == 200
    client.app.state.rabbitmq.ping = AsyncMock(side_effect=ConnectionError)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["rabbitmq"] == "unhealthy"


def test_public_auth_is_forwarded(client: TestClient) -> None:
    client.app.state.proxy.proxy = AsyncMock(return_value=JSONResponse({"ok": True}))
    assert client.post("/api/v1/auth/login", json={}).status_code == 200


def test_protected_route_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/content")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_cors_preflight_does_not_require_authentication(client: TestClient) -> None:
    response = client.options(
        "/api/v1/accounts/my",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_valid_and_invalid_jwt(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.app.state.proxy.proxy = AsyncMock(return_value=JSONResponse({"ok": True}))
    assert client.get("/api/v1/content", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/content", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_expired_jwt() -> None:
    token = make_token(exp=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(GatewayError, match="expired"):
        verify_access_token(token, Settings(jwt_public_key=PUBLIC))


@pytest.mark.asyncio
async def test_rate_limiter_per_identity_and_headers(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    limiter = RateLimiter(InMemoryRedisService())
    first = await limiter.check("ip:1", 1, 60, "one")
    second = await limiter.check("ip:1", 1, 60, "two")
    other = await limiter.check("account:1", 1, 60, "three")
    assert first.allowed and not second.allowed and other.allowed
    client.app.state.proxy.proxy = AsyncMock(return_value=JSONResponse({"ok": True}))
    assert "x-ratelimit-limit" in client.get("/api/v1/content", headers=auth_headers).headers


def test_webhook_invalid_signature(client: TestClient) -> None:
    assert client.post("/api/v1/webhooks/stripe", content=b"{}").status_code == 401


def test_webhook_publish_and_duplicate(client: TestClient) -> None:
    body = json.dumps({"id": "li-1", "type": "post.published", "data": {"id": "post"}}).encode()
    signature = hmac.new(b"linkedin-secret", body, hashlib.sha256).hexdigest()
    client.app.state.rabbitmq.publish = AsyncMock()
    first = client.post("/api/v1/webhooks/linkedin", content=body, headers={"x-webhook-signature": signature})
    second = client.post(
        "/api/v1/webhooks/linkedin", content=body, headers={"x-webhook-signature": signature}
    )
    assert first.json()["duplicate"] is False and second.json()["duplicate"] is True
    event = client.app.state.rabbitmq.publish.await_args.args[0]
    assert isinstance(event, EventEnvelope) and event.event_type == "social.post.published"


def request_for(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()],
        "state": {"request_id": "r", "correlation_id": "c"},
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_proxy_strips_trusted_headers_and_forwards_claims() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.headers)
        return httpx.Response(200, json={"success": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        proxy = ProxyService(client, {"content": "http://content"})
        request = request_for({"x-user-id": "spoofed"})
        request.state.claims = verify_access_token(make_token(), Settings(jwt_public_key=PUBLIC))
        await proxy.request_json("content", "/items", request)
    assert captured["x-user-id"] == "user-1" and captured["x-account-id"] == "account-1"


@pytest.mark.asyncio
async def test_proxy_timeout_and_downstream_error() -> None:
    async def timeout(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(GatewayError) as caught:
            await ProxyService(client, {"content": "http://content"}).request_json(
                "content", "/", request_for()
            )
        assert caught.value.status_code == 504

    async def rejected(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": {"code": "CONFLICT", "message": "Exists"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(rejected)) as client:
        with pytest.raises(GatewayError) as caught:
            await ProxyService(client, {"content": "http://content"}).request_json(
                "content", "/", request_for()
            )
        assert caught.value.code == "CONFLICT"


def test_dashboard_success_and_degraded(client: TestClient, auth_headers: dict[str, str]) -> None:
    client.app.state.proxy.request_json = AsyncMock(return_value={"value": 1})
    response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert response.status_code == 200 and len(response.json()["data"]) == 6

    async def partial(service: str, _path: str, _request: Request) -> dict[str, int]:
        if service == "usage":
            raise GatewayError(503, "DOWN", "Down")
        return {"value": 1}

    client.app.state.proxy.request_json = partial
    assert client.get("/api/v1/dashboard/overview", headers=auth_headers).json()["degraded_services"] == [
        "usage"
    ]


def test_sse_unauthorized_and_account_isolation(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/api/v1/ai/generations/g-1/stream").status_code == 401
    client.app.state.proxy.request_json = AsyncMock(return_value={"account_id": "other"})
    assert client.get("/api/v1/ai/generations/g-1/stream", headers=auth_headers).status_code == 403


@pytest.mark.asyncio
async def test_sse_heartbeat_completed_and_cleanup() -> None:
    class FakeRequest:
        calls = 0

        async def is_disconnected(self) -> bool:
            self.calls += 1
            return self.calls > 3

    class FakeRedis:
        cleaned = False

        async def subscribe(self, _channel: str) -> Any:
            try:
                await asyncio.sleep(0.02)
                yield {"data": json.dumps({"event": "completed", "data": {"text": "done"}})}
            finally:
                self.cleaned = True

    redis = FakeRedis()
    chunks = [chunk async for chunk in SSEService(redis, 0.001).stream(FakeRequest(), "a", "g")]
    assert chunks[0].startswith("event: heartbeat") and redis.cleaned


def test_event_envelope() -> None:
    event = EventEnvelope(event_type="billing.invoice.paid", correlation_id="c", payload={})
    assert event.source == "api-gateway" and event.schema_version == "1.0"
