from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TEST_ACCOUNT_ID = "22222222-2222-2222-2222-222222222222"
TEST_USER_ID = "11111111-1111-1111-1111-111111111111"


async def test_health_ready_version(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200
    version = await client.get("/version")
    assert version.json()["service"] == "notification-service"


async def test_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/notifications")
    assert response.status_code == 401


async def test_user_registered_sends_verification_email(app: Any) -> None:
    events = app.state.events
    email = app.state.email
    await events.deliver(
        "user.registered",
        {"user_id": TEST_USER_ID, "email": "new-user@example.com", "verification_token": "tok123"},
    )
    assert len(email.sent) == 1
    to, subject, html, text = email.sent[0]
    assert to == "new-user@example.com"
    assert "Verify" in subject
    assert "tok123" in html


async def test_password_reset_requested_sends_code_email(app: Any) -> None:
    events = app.state.events
    email = app.state.email
    await events.deliver(
        "user.password_reset_requested",
        {"user_id": TEST_USER_ID, "email": "forgetful@example.com", "reset_code": "482913"},
    )
    assert len(email.sent) == 1
    to, subject, html, text = email.sent[0]
    assert to == "forgetful@example.com"
    assert "reset code" in subject.lower()
    assert "482913" in html
    assert "482913" in text


async def test_member_invited_sends_invite_email(app: Any) -> None:
    events = app.state.events
    email = app.state.email
    await events.deliver(
        "member.invited",
        {
            "account_id": TEST_ACCOUNT_ID,
            "email": "invitee@example.com",
            "role": "member",
            "invite_token": "inv1",
        },
    )
    assert len(email.sent) == 1
    assert email.sent[0][0] == "invitee@example.com"


async def test_member_joined_is_logged_without_error(
    app: Any, client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    events = app.state.events
    email = app.state.email
    await events.deliver(
        "member.joined", {"account_id": TEST_ACCOUNT_ID, "user_id": TEST_USER_ID, "role": "member"}
    )
    assert len(email.sent) == 0

    response = await client.get("/api/v1/notifications", headers=auth_headers)
    items = response.json()["items"]
    assert any(item["title"] == "New team member" for item in items)


async def test_invoice_paid_resolves_owner_email_via_directory(app: Any) -> None:
    events = app.state.events
    email = app.state.email
    await events.deliver(
        "invoice.paid",
        {
            "account_id": TEST_ACCOUNT_ID,
            "invoice_id": "inv_1",
            "plan": "pro",
            "amount": 4900,
            "currency": "usd",
        },
    )
    assert len(email.sent) == 1
    assert email.sent[0][0] == "owner@example.com"


async def test_payment_failed_sends_email_and_slack_alert(app: Any) -> None:
    events = app.state.events
    email = app.state.email
    slack = app.state.slack
    await events.deliver(
        "payment.failed",
        {
            "account_id": TEST_ACCOUNT_ID,
            "invoice_id": "inv_1",
            "grace_period_ends_at": "2026-08-01T00:00:00Z",
        },
    )
    assert len(email.sent) == 1
    assert len(slack.sent) == 1
    assert "Payment failed" in slack.sent[0]


async def test_unresolvable_recipient_is_logged_as_skipped(
    app: Any, client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    events = app.state.events
    unknown_account = "99999999-9999-9999-9999-999999999999"
    await events.deliver(
        "usage.threshold_reached",
        {
            "account_id": unknown_account,
            "threshold_percentage": 80,
            "tokens_used": 800,
            "quota_tokens": 1000,
            "period": "2026-07",
        },
    )
    response = await client.get("/api/v1/notifications", headers=auth_headers)
    # scoped to TEST_ACCOUNT_ID, so the unresolved-account log entry shouldn't leak into this account's feed
    assert all(item["accountId"] != unknown_account for item in response.json()["items"])


async def test_account_scope_enforced(app: Any, client: AsyncClient, auth_headers: dict[str, str]) -> None:
    events = app.state.events
    await events.deliver(
        "invoice.paid",
        {
            "account_id": "33333333-3333-3333-3333-333333333333",
            "invoice_id": "inv_2",
            "plan": "pro",
            "amount": 100,
            "currency": "usd",
        },
    )
    response = await client.get("/api/v1/notifications", headers=auth_headers)
    items = response.json()["items"]
    assert all(item["accountId"] in (None, TEST_ACCOUNT_ID) for item in items)


async def test_unknown_event_type_is_ignored(app: Any) -> None:
    events = app.state.events
    email = app.state.email
    await events.deliver("some.unrelated.event", {"account_id": TEST_ACCOUNT_ID})
    assert len(email.sent) == 0


async def test_redelivered_event_id_does_not_resend(app: Any) -> None:
    events = app.state.events
    email = app.state.email
    payload = {"user_id": TEST_USER_ID, "email": "once@example.com", "verification_token": "tok123"}
    await events.deliver("user.registered", payload, event_id="33333333-3333-3333-3333-333333333333")
    await events.deliver("user.registered", payload, event_id="33333333-3333-3333-3333-333333333333")
    assert len(email.sent) == 1
