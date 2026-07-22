from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from conftest import ACCOUNT_ID, USER_ID
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from content_service.models import Content
from content_service.services.content import ContentService
from content_service.services.rabbitmq import InMemoryEventBus


async def create_item(client: AsyncClient, auth: dict[str, str]) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/content",
        headers=auth,
        json={"title": "Launch post", "body": "Draft copy", "content_type": "post"},
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


async def test_operations_and_auth(context: dict[str, Any]) -> None:
    client = cast(AsyncClient, context["client"])
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).json()["status"] == "ready"
    assert (await client.get("/version")).json()["service"] == "content-service"
    assert (await client.get("/api/v1/content")).status_code == 401


async def test_create_list_get_update_and_versions(context: dict[str, Any], auth: dict[str, str]) -> None:
    client = cast(AsyncClient, context["client"])
    sessions = cast(async_sessionmaker[AsyncSession], context["sessions"])
    item = await create_item(client, auth)
    listed = await client.get("/api/v1/content", headers=auth)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["title"] == "Launch post"

    fetched = await client.get(f"/api/v1/content/{item['id']}", headers=auth)
    assert fetched.status_code == 200

    updated = await client.patch(
        f"/api/v1/content/{item['id']}",
        headers=auth,
        json={"body": "Improved copy", "title": "Launch post v2"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    async with sessions() as session:
        assert await ContentService.versions_count(session, uuid4()) == 0
        assert await ContentService.versions_count(session, UUID(str(item["id"]))) == 2


async def test_upload_approve_publish_delete_rules(context: dict[str, Any], auth: dict[str, str]) -> None:
    client = cast(AsyncClient, context["client"])
    item = await create_item(client, auth)
    upload = await client.post(
        f"/api/v1/content/{item['id']}/image",
        headers=auth,
        files={"file": ("image.png", b"fake image bytes", "image/png")},
    )
    assert upload.status_code == 200
    assert upload.json()["image_url"].endswith(".png")

    approved = await client.post(f"/api/v1/content/{item['id']}/approve", headers=auth)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    denied = await client.post(
        f"/api/v1/content/{item['id']}/publish",
        headers={"Authorization": "Bearer member"},
    )
    assert denied.status_code == 403

    published = await client.post(f"/api/v1/content/{item['id']}/publish", headers=auth)
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert (await client.delete(f"/api/v1/content/{item['id']}", headers=auth)).status_code == 409
    assert (
        await client.patch(f"/api/v1/content/{item['id']}", headers=auth, json={"body": "edit"})
    ).status_code == 409


async def test_account_scope_and_superadmin(context: dict[str, Any], auth: dict[str, str]) -> None:
    client = cast(AsyncClient, context["client"])
    item = await create_item(client, auth)
    assert (
        await client.get(f"/api/v1/content/{item['id']}", headers={"Authorization": "Bearer other"})
    ).status_code == 403
    assert (
        await client.get(f"/api/v1/content/{item['id']}", headers={"Authorization": "Bearer super"})
    ).status_code == 200


async def test_ai_generation_completed_consumer(context: dict[str, Any]) -> None:
    sessions = cast(async_sessionmaker[AsyncSession], context["sessions"])
    events = cast(InMemoryEventBus, context["events"])
    event = {
        "event_id": str(uuid4()),
        "event_type": "ai.generation_completed",
        "correlation_id": str(uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {
            "generation_id": str(uuid4()),
            "generation_type": "post",
            "account_id": str(ACCOUNT_ID),
            "user_id": str(USER_ID),
            "prompt": "Announce analytics",
            "response": "Here is the generated post.",
            "image_url": "http://images.local/post.png",
            "image_asset_ref": "post.png",
            "model": "openai/gpt-4.1-mini",
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "total_tokens": 20,
            "cost_microusd": 100,
        },
    }
    await events.deliver(event)
    await events.deliver(event)
    async with sessions() as session:
        rows = list((await session.scalars(select(Content))).all())
    assert len(rows) == 1
    assert rows[0].title == "Announce analytics"
    assert len(events.events) == 1
