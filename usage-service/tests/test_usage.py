from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from conftest import ACCOUNT_ID, OTHER_ACCOUNT_ID, USER_ID
from usage_service.core.config import Settings
from usage_service.core.errors import UsageError
from usage_service.services.identity import INTERNAL_SERVICE_ID, JWTIdentityService
from usage_service.services.rabbitmq import InMemoryEventBus
from usage_service.services.redis import InMemoryRedisService
from usage_service.services.usage import UsageService, monthly_period


def test_internal_service_token_grants_superadmin_identity() -> None:
    settings = Settings(_env_file=None, internal_service_token="shared-secret")  # noqa: S106
    identity = JWTIdentityService(settings).verify("shared-secret")
    assert identity.is_superadmin
    assert identity.user_id == INTERNAL_SERVICE_ID

    with pytest.raises(UsageError) as invalid:
        JWTIdentityService(settings).verify("wrong-token")
    assert invalid.value.code == "INVALID_TOKEN"


def generation_event(tokens: int, *, model: str = "openai/gpt-4.1") -> dict[str, Any]:
    prompt = tokens // 2
    return {
        "event_id": str(uuid4()),
        "event_type": "ai.generation_completed",
        "correlation_id": str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {
            "generation_id": str(uuid4()),
            "account_id": str(ACCOUNT_ID),
            "user_id": str(USER_ID),
            "model": model,
            "prompt_tokens": prompt,
            "completion_tokens": tokens - prompt,
            "total_tokens": tokens,
            "cost_microusd": tokens * 10,
        },
    }


async def test_operations_auth_and_quota_check(context: dict[str, Any], auth: dict[str, str]) -> None:
    client = cast(AsyncClient, context["client"])
    assert (await client.get("/health")).status_code == 200
    ready = await client.get("/ready")
    assert ready.status_code == 200 and all(ready.json()["checks"].values())
    assert (await client.get("/version")).json()["service"] == "usage-service"
    assert (await client.get("/api/v1/usage/summary")).status_code == 401

    allowed = await client.post("/api/v1/usage/quota/check", headers=auth, json={"estimated_tokens": 600})
    denied = await client.post("/api/v1/usage/quota/check", headers=auth, json={"estimated_tokens": 500})
    assert allowed.json()["allowed"] is True
    assert allowed.json()["remaining_tokens"] == 400
    assert denied.json()["allowed"] is False


async def test_event_ledger_reconciliation_thresholds_and_summary(
    context: dict[str, Any], auth: dict[str, str]
) -> None:
    app = cast(FastAPI, context["app"])
    usage = cast(UsageService, app.state.usage)
    events = cast(InMemoryEventBus, context["events"])
    redis = cast(InMemoryRedisService, context["redis"])
    first = generation_event(800)
    await usage.consume(first)
    await usage.consume(first)
    await usage.consume(generation_event(200, model="anthropic/claude-sonnet"))

    summary = await usage.summary(ACCOUNT_ID)
    assert summary.tokens_used == 1000
    assert summary.cost_microusd == 10000
    assert summary.generations == 2
    assert len(summary.by_model) == 2 and len(summary.daily) == 1
    assert [event.payload["threshold_percentage"] for event in events.events] == [80, 100]
    start, _ = monthly_period()
    assert redis.counters[usage.quota_key(ACCOUNT_ID, start)] == 1000

    client = cast(AsyncClient, context["client"])
    response = await client.get("/api/v1/usage/summary", headers=auth)
    assert response.status_code == 200 and response.json()["quota_percentage"] == 100
    ledger = await client.get("/api/v1/usage/ledger?limit=1", headers=auth)
    assert ledger.status_code == 200 and len(ledger.json()) == 1


async def test_account_scope_and_invalid_events(context: dict[str, Any], auth: dict[str, str]) -> None:
    client = cast(AsyncClient, context["client"])
    denied = await client.get(f"/api/v1/usage/summary?account_id={OTHER_ACCOUNT_ID}", headers=auth)
    assert denied.status_code == 403
    allowed = await client.get(
        f"/api/v1/usage/summary?account_id={OTHER_ACCOUNT_ID}",
        headers={"Authorization": "Bearer superadmin"},
    )
    assert allowed.status_code == 200 and allowed.json()["tokens_used"] == 0

    usage = cast(UsageService, cast(FastAPI, context["app"]).state.usage)
    with pytest.raises(UsageError) as unsupported:
        await usage.consume({"event_type": "something.else", "payload": {}})
    assert unsupported.value.code == "UNSUPPORTED_EVENT"
    invalid = generation_event(10)
    invalid["payload"]["total_tokens"] = 11
    with pytest.raises(UsageError) as malformed:
        await usage.consume(invalid)
    assert malformed.value.code == "INVALID_USAGE_EVENT"
