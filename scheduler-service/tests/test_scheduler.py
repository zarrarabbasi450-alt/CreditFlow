import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, update

from scheduler_service.models import ProcessedEvent, ScheduledPost, utcnow


@pytest.mark.asyncio
async def test_health_ready_version(client) -> None:
    assert (await client.get("/health")).json()["status"] == "ok"
    assert (await client.get("/ready")).json()["status"] == "ready"
    assert (await client.get("/version")).json()["service"] == "scheduler-service"


@pytest.mark.asyncio
async def test_schedule_calendar_reschedule_cancel(client, auth_headers) -> None:
    publish_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    created = (
        await client.post(
            "/api/v1/scheduler",
            headers=auth_headers,
            json={
                "content_id": "33333333-3333-3333-3333-333333333333",
                "title": "Launch post",
                "publish_at": publish_at,
                "timezone": "Asia/Karachi",
            },
        )
    ).json()
    assert created["title"] == "Launch post"
    assert created["status"] == "scheduled"
    assert created["publish_at_local"].endswith("+05:00")

    calendar = (
        await client.get(
            "/api/v1/scheduler",
            headers=auth_headers,
            params={
                "start": datetime.now(UTC).isoformat(),
                "end": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "timezone": "Asia/Karachi",
            },
        )
    ).json()
    assert len(calendar["items"]) == 1

    updated = (
        await client.patch(
            f"/api/v1/scheduler/{created['id']}",
            headers=auth_headers,
            json={"publish_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(), "timezone": "UTC"},
        )
    ).json()
    assert updated["timezone"] == "UTC"

    cancelled = (await client.delete(f"/api/v1/scheduler/{created['id']}", headers=auth_headers)).json()
    assert cancelled["status"] == "cancelled"


@pytest.mark.asyncio
async def test_content_deleted_event_cancels_active_schedule(app, client, auth_headers) -> None:
    content_id = "44444444-4444-4444-4444-444444444444"
    publish_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    created = (
        await client.post(
            "/api/v1/scheduler",
            headers=auth_headers,
            json={
                "content_id": content_id,
                "title": "Launch post",
                "publish_at": publish_at,
                "timezone": "UTC",
            },
        )
    ).json()
    assert created["status"] == "scheduled"

    await app.state.scheduler.consume({
        "event_type": "content.deleted",
        "payload": {"content_id": content_id, "account_id": "22222222-2222-2222-2222-222222222222"},
    })

    fetched = (
        await client.get(
            "/api/v1/scheduler",
            headers=auth_headers,
            params={
                "start": datetime.now(UTC).isoformat(),
                "end": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "timezone": "UTC",
            },
        )
    ).json()
    matching = [item for item in fetched["items"] if item["id"] == created["id"]]
    assert matching[0]["status"] == "cancelled"

    # A second delivery (at-least-once redelivery) must not error on an
    # already-cancelled schedule.
    await app.state.scheduler.consume({
        "event_type": "content.deleted",
        "payload": {"content_id": content_id, "account_id": "22222222-2222-2222-2222-222222222222"},
    })

    # An event with no matching schedule is a no-op, not an error.
    await app.state.scheduler.consume({
        "event_type": "content.deleted",
        "payload": {"content_id": "55555555-5555-5555-5555-555555555555"},
    })


@pytest.mark.asyncio
async def test_consume_is_idempotent_on_event_id(app, client, auth_headers) -> None:
    content_id = "66666666-6666-6666-6666-666666666666"
    publish_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    await client.post(
        "/api/v1/scheduler",
        headers=auth_headers,
        json={
            "content_id": content_id,
            "title": "Launch post",
            "publish_at": publish_at,
            "timezone": "UTC",
        },
    )
    event = {
        "event_id": "77777777-7777-7777-7777-777777777777",
        "event_type": "content.deleted",
        "payload": {"content_id": content_id, "account_id": "22222222-2222-2222-2222-222222222222"},
    }
    await app.state.scheduler.consume(event)
    await app.state.scheduler.consume(event)
    async with app.state.scheduler.sessions() as session:
        rows = list((await session.scalars(select(ProcessedEvent))).all())
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_reject_past_publish_at(client, auth_headers) -> None:
    response = await client.post(
        "/api/v1/scheduler",
        headers=auth_headers,
        json={
            "content_id": "33333333-3333-3333-3333-333333333333",
            "title": "Past post",
            "publish_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_content_can_have_only_one_active_schedule(client, auth_headers) -> None:
    content_id = "33333333-3333-3333-3333-333333333333"
    first = await client.post(
        "/api/v1/scheduler",
        headers=auth_headers,
        json={
            "content_id": content_id,
            "title": "Launch post",
            "publish_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert first.status_code == 200

    duplicate = await client.post(
        "/api/v1/scheduler",
        headers=auth_headers,
        json={
            "content_id": content_id,
            "title": "Launch post again",
            "publish_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONTENT_ALREADY_SCHEDULED"

    await client.delete(f"/api/v1/scheduler/{first.json()['id']}", headers=auth_headers)
    replacement = await client.post(
        "/api/v1/scheduler",
        headers=auth_headers,
        json={
            "content_id": content_id,
            "title": "Launch post replacement",
            "publish_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert replacement.status_code == 200


@pytest.mark.asyncio
async def test_due_item_fires_once(app, client, auth_headers) -> None:
    created = (
        await client.post(
            "/api/v1/scheduler",
            headers=auth_headers,
            json={
                "content_id": "33333333-3333-3333-3333-333333333333",
                "title": "Due post",
                "publish_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "timezone": "UTC",
            },
        )
    ).json()
    async with app.state.scheduler.sessions() as session:
        await session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.id == UUID(created["id"]))
            .values(publish_at=utcnow() - timedelta(seconds=1))
        )
        await session.commit()
    await asyncio.sleep(0)
    await app.state.scheduler.fire_due()
    await app.state.scheduler.fire_due()
    events = app.state.events.events
    assert len(events) == 1
    assert events[0].event_type == "content.scheduled"
    assert events[0].payload["scheduled_post_id"] == created["id"]
