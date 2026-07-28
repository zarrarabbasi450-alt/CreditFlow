from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_ready_version(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200
    version = await client.get("/version")
    assert version.json()["service"] == "scraper-service"


async def test_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/scraper/jobs")
    assert response.status_code == 401


async def test_create_url_job_runs_synchronously_and_stores_document(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/scraper/jobs",
        json={
            "job_type": "url",
            "target": "https://example.com/blog",
            "name": "Competitor blog",
            "max_pages": 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "completed"
    assert job["pages_processed"] == 1
    assert job["answer"] is not None
    assert "<h1>" in job["answer_html"]

    documents = await client.get(f"/api/v1/scraper/jobs/{job['id']}/documents", headers=auth_headers)
    assert documents.status_code == 200
    body = documents.json()
    assert body[0]["title"] == "Example title"
    assert body[0]["job_type"] == "url"


async def test_create_serp_job_stores_organic_results(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/scraper/jobs",
        json={"job_type": "serp", "target": "competitor pricing trends", "name": "Pricing trends"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "completed"

    documents = await client.get(f"/api/v1/scraper/jobs/{job['id']}/documents", headers=auth_headers)
    data = documents.json()[0]["data"]
    assert data["organic_results"][0]["title"] == "Competitor result"


async def test_research_job_synthesizes_markdown_answer(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/scraper/jobs",
        json={"job_type": "research", "target": "gold prices", "name": "Gold prices research"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "completed"
    assert job["max_pages"] == 4
    assert job["answer"] is not None
    assert job["answer"].startswith("# gold prices")
    assert "<h1>" in job["answer_html"]

    documents = await client.get(f"/api/v1/scraper/jobs/{job['id']}/documents", headers=auth_headers)
    assert documents.json()[0]["job_type"] == "research"


async def test_invalid_url_target_is_rejected(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/scraper/jobs",
        json={"job_type": "url", "target": "not-a-url", "name": "Bad target"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_recurring_without_interval_rejected(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/scraper/jobs",
        json={"job_type": "serp", "target": "trend", "name": "Daily trend", "recurring": True},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_recurring_job_schedules_next_run(
    app: Any, client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/scraper/jobs",
        json={
            "job_type": "serp",
            "target": "daily competitor check",
            "name": "Daily competitor check",
            "recurring": True,
            "interval_hours": 24,
        },
        headers=auth_headers,
    )
    job = response.json()
    assert job["recurring"] is True
    assert job["next_run_at"] is not None


async def test_due_recurring_job_is_rescanned_and_reexecuted(app: Any) -> None:
    scraper = app.state.scraper
    from scraper_service.schemas.scraper import ScraperJobCreate
    from scraper_service.services.identity import Identity

    identity = Identity(
        user_id=__import__("uuid").UUID("11111111-1111-1111-1111-111111111111"),
        account_id=__import__("uuid").UUID("22222222-2222-2222-2222-222222222222"),
        account_role="Owner",
    )
    created = await scraper.create(
        ScraperJobCreate(
            job_type="serp", target="weekly trend", name="Weekly", recurring=True, interval_hours=1
        ),
        identity,
    )
    job = await app.state.repository.get_job(created.id)
    job.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
    await app.state.repository.replace_job(job)

    rescanned = await scraper.scan_due_recurring_jobs()
    assert rescanned == 1
    refreshed = await app.state.repository.get_job(created.id)
    assert refreshed.status == "completed"
    assert refreshed.attempts == 2


async def test_consume_is_idempotent_on_event_id(app: Any) -> None:
    from scraper_service.schemas.scraper import ScraperJobCreate
    from scraper_service.services.identity import Identity

    identity = Identity(
        user_id=__import__("uuid").UUID("11111111-1111-1111-1111-111111111111"),
        account_id=__import__("uuid").UUID("22222222-2222-2222-2222-222222222222"),
        account_role="Owner",
    )
    scraper = app.state.scraper
    created = await scraper.create(
        ScraperJobCreate(job_type="serp", target="idempotency check", name="Idempotency"), identity
    )
    event_id = "77777777-7777-7777-7777-777777777777"
    event = {"event_id": event_id, "event_type": "scrape.requested", "payload": {"job_id": str(created.id)}}

    # First delivery executes the job.
    await scraper.consume(event)
    first_run = await app.state.repository.get_job(created.id)
    assert first_run.attempts == 1

    # Redelivery of the same event_id must not re-execute, even if the job were
    # somehow put back in a "queued" state (the job-status check alone wouldn't
    # catch this — the event_id ledger is what actually prevents it).
    first_run.status = "queued"
    await app.state.repository.replace_job(first_run)
    await scraper.consume(event)
    second_check = await app.state.repository.get_job(created.id)
    assert second_check.attempts == 1


async def test_cancel_requires_owner_or_admin_and_queued_status(
    app: Any, client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/scraper/jobs",
        json={"job_type": "serp", "target": "x", "name": "Job x"},
        headers=auth_headers,
    )
    job_id = response.json()["id"]
    cancel = await client.post(f"/api/v1/scraper/jobs/{job_id}/cancel", headers=auth_headers)
    assert cancel.status_code == 409


async def test_account_scope_enforced(app: Any, client: AsyncClient, auth_headers: dict[str, str]) -> None:
    created = await client.post(
        "/api/v1/scraper/jobs",
        json={"job_type": "serp", "target": "x", "name": "Job x"},
        headers=auth_headers,
    )
    job_id = created.json()["id"]
    from uuid import UUID

    job = await app.state.repository.get_job(UUID(job_id))
    job.account_id = UUID("99999999-9999-9999-9999-999999999999")
    await app.state.repository.replace_job(job)

    response = await client.get(f"/api/v1/scraper/jobs/{job_id}", headers=auth_headers)
    assert response.status_code == 403
