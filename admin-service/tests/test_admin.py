from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient

from admin_service.schemas.admin import SessionItem

pytestmark = pytest.mark.asyncio

TENANT_ACCOUNT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT_USER_ID = UUID("33333333-3333-3333-3333-333333333333")
OTHER_ACCOUNT_ID = UUID("44444444-4444-4444-4444-444444444444")


async def test_health_ready_version(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200
    version = await client.get("/version")
    assert version.json()["service"] == "admin-service"


async def test_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/overview")).status_code == 401
    assert (await client.get("/api/v1/admin/sessions")).status_code == 401


async def test_session_listing_scoped_by_account(
    app: Any, client: AsyncClient, tenant_headers: dict[str, str]
) -> None:
    session_directory = app.state.session_directory
    session_directory.sessions["jti-tenant"] = SessionItem(
        jti="jti-tenant",
        user_id=TENANT_USER_ID,
        account_id=TENANT_ACCOUNT_ID,
        account_role="Owner",
        platform_role=None,
    )
    session_directory.sessions["jti-other"] = SessionItem(
        jti="jti-other",
        user_id=TENANT_USER_ID,
        account_id=OTHER_ACCOUNT_ID,
        account_role="Owner",
        platform_role=None,
    )
    response = await client.get("/api/v1/admin/sessions", headers=tenant_headers)
    assert response.status_code == 200
    jtis = {item["jti"] for item in response.json()}
    assert jtis == {"jti-tenant"}


async def test_superadmin_sees_all_sessions(
    app: Any, client: AsyncClient, superadmin_headers: dict[str, str]
) -> None:
    session_directory = app.state.session_directory
    session_directory.sessions["jti-a"] = SessionItem(
        jti="jti-a",
        user_id=TENANT_USER_ID,
        account_id=TENANT_ACCOUNT_ID,
        account_role="Owner",
        platform_role=None,
    )
    session_directory.sessions["jti-b"] = SessionItem(
        jti="jti-b",
        user_id=TENANT_USER_ID,
        account_id=OTHER_ACCOUNT_ID,
        account_role="Owner",
        platform_role=None,
    )
    response = await client.get("/api/v1/admin/sessions", headers=superadmin_headers)
    jtis = {item["jti"] for item in response.json()}
    assert jtis == {"jti-a", "jti-b"}


async def test_tenant_cannot_query_other_account_sessions(
    app: Any, client: AsyncClient, tenant_headers: dict[str, str]
) -> None:
    del app
    response = await client.get(
        "/api/v1/admin/sessions", params={"account_id": str(OTHER_ACCOUNT_ID)}, headers=tenant_headers
    )
    assert response.status_code == 403


async def test_revoke_session_enforces_account_scope(
    app: Any, client: AsyncClient, tenant_headers: dict[str, str]
) -> None:
    session_directory = app.state.session_directory
    session_directory.sessions["jti-other"] = SessionItem(
        jti="jti-other",
        user_id=TENANT_USER_ID,
        account_id=OTHER_ACCOUNT_ID,
        account_role="Owner",
        platform_role=None,
    )
    forbidden = await client.delete("/api/v1/admin/sessions/jti-other", headers=tenant_headers)
    assert forbidden.status_code == 403
    assert "jti-other" in session_directory.sessions

    missing = await client.delete("/api/v1/admin/sessions/does-not-exist", headers=tenant_headers)
    assert missing.status_code == 404


async def test_revoke_session_success(app: Any, client: AsyncClient, tenant_headers: dict[str, str]) -> None:
    session_directory = app.state.session_directory
    session_directory.sessions["jti-mine"] = SessionItem(
        jti="jti-mine",
        user_id=TENANT_USER_ID,
        account_id=TENANT_ACCOUNT_ID,
        account_role="Owner",
        platform_role=None,
    )
    response = await client.delete("/api/v1/admin/sessions/jti-mine", headers=tenant_headers)
    assert response.status_code == 204
    assert "jti-mine" not in session_directory.sessions


async def test_account_summary_scoped(client: AsyncClient, tenant_headers: dict[str, str]) -> None:
    response = await client.get(
        f"/api/v1/admin/accounts/{TENANT_ACCOUNT_ID}/summary", headers=tenant_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan_tier"] == "pro"
    assert body["credit_balance"] == 1000
    assert body["usage_tokens"] == 200

    forbidden = await client.get(
        f"/api/v1/admin/accounts/{OTHER_ACCOUNT_ID}/summary", headers=tenant_headers
    )
    assert forbidden.status_code == 403


async def test_audit_consume_and_scoped_listing(
    app: Any, client: AsyncClient, tenant_headers: dict[str, str], superadmin_headers: dict[str, str]
) -> None:
    events = app.state.events
    await events.deliver(
        "invoice.paid",
        {"account_id": str(TENANT_ACCOUNT_ID), "invoice_id": "inv_1", "plan": "pro"},
        event_id="99999999-9999-9999-9999-999999999991",
    )
    await events.deliver(
        "member.invited",
        {"account_id": str(OTHER_ACCOUNT_ID), "email": "someone@example.com"},
        event_id="99999999-9999-9999-9999-999999999992",
    )
    # duplicate delivery of the same event_id must not create a second row
    await events.deliver(
        "invoice.paid",
        {"account_id": str(TENANT_ACCOUNT_ID), "invoice_id": "inv_1", "plan": "pro"},
        event_id="99999999-9999-9999-9999-999999999991",
    )

    tenant_view = await client.get("/api/v1/admin/audit", headers=tenant_headers)
    assert tenant_view.status_code == 200
    tenant_actions = [item["action"] for item in tenant_view.json()]
    assert tenant_actions.count("invoice.paid") == 1
    assert "member.invited" not in tenant_actions

    admin_view = await client.get("/api/v1/admin/audit", headers=superadmin_headers)
    admin_actions = {item["action"] for item in admin_view.json()}
    assert admin_actions == {"invoice.paid", "member.invited"}


async def test_unknown_event_without_type_is_ignored(
    app: Any, client: AsyncClient, superadmin_headers: dict[str, str]
) -> None:
    events = app.state.events
    await events.deliver("", {"account_id": str(TENANT_ACCOUNT_ID)}, event_id="evt-empty")
    response = await client.get("/api/v1/admin/audit", headers=superadmin_headers)
    assert response.json() == []


async def test_overview_combines_audit_and_health(
    app: Any, client: AsyncClient, superadmin_headers: dict[str, str]
) -> None:
    events = app.state.events
    await events.deliver("post.published", {"account_id": str(TENANT_ACCOUNT_ID)}, event_id="evt-post")
    response = await client.get("/api/v1/admin/overview", headers=superadmin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["health"][0]["service"] == "auth-service"
    assert any(entry["action"] == "post.published" for entry in body["audit"])
    assert body["flags"] == []
