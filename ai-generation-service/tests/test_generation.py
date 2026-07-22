import asyncio
from collections.abc import AsyncIterator
from typing import Any, cast

from httpx import AsyncClient

from ai_generation_service.core.errors import AIServiceError
from ai_generation_service.services.rabbitmq import InMemoryEventBus
from ai_generation_service.services.redis import InMemoryRedisService
from ai_generation_service.services.usage import InMemoryUsageClient


class FallbackAIProvider:
    async def stream_completion(self, model: str, prompt: str) -> AsyncIterator[str]:
        del prompt
        if model == "openai/gpt-4o":
            raise AIServiceError(502, "MODEL_UNAVAILABLE", "Primary model is unavailable")
        for token in ["Fallback", " worked"]:
            yield token

    async def close(self) -> None:
        return None


async def test_operations_and_auth_required(context: dict[str, Any]) -> None:
    client = cast(AsyncClient, context["client"])
    assert (await client.get("/health")).json() == {"status": "ok"}
    assert (await client.get("/ready")).status_code == 200
    assert (await client.get("/version")).json()["service"] == "ai-generation-service"
    assert (await client.post("/api/v1/ai/generations", json={"prompt": "hello"})).status_code == 401


async def test_generation_persists_history_and_publishes_events(
    context: dict[str, Any], auth: dict[str, str]
) -> None:
    client = cast(AsyncClient, context["client"])
    response = await client.post(
        "/api/v1/ai/generations",
        headers=auth,
        json={"prompt": "Write a launch post", "model": "fast", "generate_image": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["image_url"].startswith("https://image.pollinations.ai/prompt/")

    job = await client.get(f"/api/v1/ai/generations/{body['job_id']}", headers=auth)
    for _ in range(20):
        if job.json()["status"] == "completed":
            break
        await asyncio.sleep(0.05)
        job = await client.get(f"/api/v1/ai/generations/{body['job_id']}", headers=auth)
    assert job.status_code == 200
    assert job.json()["response"] == "Hello from CreditFlow"
    ownership = await client.get(f"/internal/generations/{body['job_id']}/ownership")
    assert ownership.json()["account_id"]
    history = await client.get("/api/v1/ai/history", headers=auth)
    assert history.status_code == 200 and len(history.json()) == 1
    redis = cast(InMemoryRedisService, context["redis"])
    stream_events = redis.messages[f"ai:stream:{job.json()['account_id']}:{body['job_id']}"]
    assert [event["event"] for event in stream_events] == ["token", "token", "token", "completed"]
    events = cast(InMemoryEventBus, context["events"]).events
    assert [event.event_type for event in events] == ["ai.generation_completed"]


async def test_quota_denial_blocks_generation(context: dict[str, Any], auth: dict[str, str]) -> None:
    cast(InMemoryUsageClient, context["usage"]).allowed = False
    client = cast(AsyncClient, context["client"])
    response = await client.post("/api/v1/ai/generations", headers=auth, json={"prompt": "No quota"})
    assert response.status_code == 402


async def test_generation_falls_back_when_primary_model_is_unavailable(
    context: dict[str, Any], auth: dict[str, str]
) -> None:
    context["app"].state.generations.ai = FallbackAIProvider()
    client = cast(AsyncClient, context["client"])
    response = await client.post(
        "/api/v1/ai/generations",
        headers=auth,
        json={"prompt": "Write a quality post", "model": "quality"},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = await client.get(f"/api/v1/ai/generations/{job_id}", headers=auth)
    for _ in range(20):
        if job.json()["status"] == "completed":
            break
        await asyncio.sleep(0.05)
        job = await client.get(f"/api/v1/ai/generations/{job_id}", headers=auth)
    body = job.json()
    assert body["model"] == "openai/gpt-4o-mini"
    assert body["response"] == "Fallback worked"


async def test_cancel_sets_cancel_marker(context: dict[str, Any], auth: dict[str, str]) -> None:
    client = cast(AsyncClient, context["client"])
    created = await client.post("/api/v1/ai/generations", headers=auth, json={"prompt": "Cancel me"})
    job_id = created.json()["job_id"]
    cancelled = await client.post(f"/api/v1/ai/generations/{job_id}/cancel", headers=auth)
    assert cancelled.status_code == 200
    assert await cast(InMemoryRedisService, context["redis"]).is_cancelled(job_id)


async def test_image_endpoint(context: dict[str, Any], auth: dict[str, str]) -> None:
    client = cast(AsyncClient, context["client"])
    response = await client.post(
        "/api/v1/ai/images", headers=auth, json={"prompt": "A clean content dashboard"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
