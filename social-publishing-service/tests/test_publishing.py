from uuid import UUID

import pytest
from cryptography.fernet import Fernet

from social_publishing_service.services.crypto import TokenCipher


@pytest.mark.asyncio
async def test_health_ready_version(client) -> None:
    assert (await client.get("/health")).json()["status"] == "ok"
    assert (await client.get("/ready")).json()["status"] == "ready"
    assert (await client.get("/version")).json()["service"] == "social-publishing-service"


@pytest.mark.asyncio
async def test_dev_connection_and_manual_publish(client, auth_headers) -> None:
    connected = await client.post(
        "/api/v1/publishing/linkedin/dev-connect",
        headers=auth_headers,
        json={"profile_name": "Zarrar LinkedIn", "profile_url": "https://linkedin.com/in/zarrar"},
    )
    assert connected.status_code == 200
    connection_id = connected.json()["id"]

    published = await client.post(
        "/api/v1/publishing/linkedin",
        headers=auth_headers,
        json={"connection_id": connection_id, "caption": "Hello LinkedIn from CreditFlow"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["linkedin_post_id"].startswith("dev-linkedin")

    collection = (await client.get("/api/v1/publishing", headers=auth_headers)).json()
    assert collection["connections"][0]["status"] == "connected"
    assert collection["jobs"][0]["status"] == "published"


@pytest.mark.asyncio
async def test_oauth_callback_encrypts_tokens_and_publishes_with_image(client, app, auth_headers) -> None:
    app.state.publishing.cipher = TokenCipher(Fernet.generate_key().decode())
    started = await client.post("/api/v1/publishing/linkedin/connect", headers=auth_headers)
    assert started.status_code == 200
    state = started.json()["state"]

    callback = await client.get(f"/api/v1/publishing/linkedin/callback?state={state}&code=oauth-code&response=json")
    assert callback.status_code == 200
    connection = callback.json()
    assert connection["status"] == "connected"
    assert connection["profile_urn"] == "urn:li:person:test"

    published = await client.post(
        "/api/v1/publishing/linkedin",
        headers=auth_headers,
        json={
            "connection_id": connection["id"],
            "caption": "Real OAuth publish path",
            "image_url": "https://example.com/image.png",
        },
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["linkedin_post_id"] == "linkedin-post-id"


@pytest.mark.asyncio
async def test_refresh_linkedin_tokens(client, app, auth_headers) -> None:
    app.state.publishing.cipher = TokenCipher(Fernet.generate_key().decode())
    started = await client.post("/api/v1/publishing/linkedin/connect", headers=auth_headers)
    state = started.json()["state"]
    await client.get(f"/api/v1/publishing/linkedin/callback?state={state}&code=oauth-code&response=json")

    refreshed = await client.post("/api/v1/publishing/linkedin/refresh-tokens", headers=auth_headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["refreshed"] == 1


@pytest.mark.asyncio
async def test_publish_existing_content(client, auth_headers) -> None:
    connected = (
        await client.post(
            "/api/v1/publishing/linkedin/dev-connect",
            headers=auth_headers,
            json={"profile_name": "Zarrar LinkedIn", "profile_url": "https://linkedin.com/in/zarrar"},
        )
    ).json()
    published = await client.post(
        "/api/v1/publishing/linkedin/content",
        headers=auth_headers,
        json={
            "connection_id": connected["id"],
            "content_id": "44444444-4444-4444-4444-444444444444",
            "caption": "Approved content override",
        },
    )
    assert published.status_code == 200
    assert published.json()["content_id"] == "44444444-4444-4444-4444-444444444444"


@pytest.mark.asyncio
async def test_content_scheduled_event_creates_publish_job(app, client, auth_headers) -> None:
    connected = await client.post(
        "/api/v1/publishing/linkedin/dev-connect",
        headers=auth_headers,
        json={"profile_name": "CreditFlow Page", "profile_url": "https://linkedin.com/company/creditflow"},
    )
    assert connected.status_code == 200

    await app.state.events.deliver(
        {
            "event_type": "content.scheduled",
            "payload": {
                "scheduled_post_id": "33333333-3333-3333-3333-333333333333",
                "account_id": "22222222-2222-2222-2222-222222222222",
                "content_id": "44444444-4444-4444-4444-444444444444",
            },
        }
    )
    events = app.state.events.events
    assert events[-1].event_type == "post.published"
    assert events[-1].payload["scheduled_post_id"] == "33333333-3333-3333-3333-333333333333"


@pytest.mark.asyncio
async def test_content_scheduled_consume_is_idempotent_on_event_id(app, client, auth_headers) -> None:
    await client.post(
        "/api/v1/publishing/linkedin/dev-connect",
        headers=auth_headers,
        json={"profile_name": "CreditFlow Page", "profile_url": "https://linkedin.com/company/creditflow"},
    )
    scheduled_event = {
        "event_id": "55555555-5555-5555-5555-555555555555",
        "event_type": "content.scheduled",
        "payload": {
            "scheduled_post_id": "66666666-6666-6666-6666-666666666666",
            "account_id": "22222222-2222-2222-2222-222222222222",
            "content_id": "44444444-4444-4444-4444-444444444444",
        },
    }
    # A redelivered event_id must not publish the same content to LinkedIn twice.
    await app.state.events.deliver(scheduled_event)
    await app.state.events.deliver(scheduled_event)
    published_events = [event for event in app.state.events.events if event.event_type == "post.published"]
    assert len(published_events) == 1


@pytest.mark.asyncio
async def test_disconnect_connection(client, auth_headers) -> None:
    connected = (
        await client.post(
            "/api/v1/publishing/linkedin/dev-connect",
            headers=auth_headers,
            json={"profile_name": "Zarrar", "profile_url": "https://linkedin.com/in/zarrar"},
        )
    ).json()
    response = await client.delete(
        f"/api/v1/publishing/connections/{UUID(connected['id'])}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "LinkedIn connection revoked"


@pytest.mark.asyncio
async def test_protected_routes_require_authentication(client) -> None:
    response = await client.get("/api/v1/publishing")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_oauth_callback_error_redirects_to_frontend(client, auth_headers) -> None:
    started = await client.post("/api/v1/publishing/linkedin/connect", headers=auth_headers)
    state = started.json()["state"]
    response = await client.get(
        "/api/v1/publishing/linkedin/callback"
        f"?state={state}&error=unauthorized_scope_error&error_description=Scope%20is%20not%20authorized",
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert "/publishing/linkedin?linkedin=error" in response.headers["location"]
