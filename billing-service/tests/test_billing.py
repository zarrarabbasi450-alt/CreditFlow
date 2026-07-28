from uuid import uuid4

import pytest
from httpx import AsyncClient

from billing_service.api.dependencies import require_owner
from billing_service.core.errors import BillingError
from billing_service.services.identity import Identity


async def test_operations(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200
    assert (await client.get("/version")).status_code == 200
    assert (await client.get("/docs")).status_code == 200


async def test_owner_billing_flow(client: AsyncClient, auth: dict[str, str]) -> None:
    overview = await client.get("/api/v1/billing/overview", headers=auth)
    assert overview.status_code == 200 and overview.json()["subscription"]["plan"] == "free"
    checkout = await client.post("/api/v1/billing/checkout", headers=auth, json={"plan": "pro", "seats": 1})
    assert checkout.status_code == 200
    assert checkout.json()["url"].startswith("https://checkout.stripe.test")
    portal = await client.post("/api/v1/billing/portal", headers=auth)
    assert portal.json()["url"].startswith("https://billing.stripe.test")
    credit_checkout = await client.post(
        "/api/v1/billing/credits/checkout", headers=auth, json={"credits": 500}
    )
    assert credit_checkout.status_code == 200
    assert "credits=500" in credit_checkout.json()["url"]


async def test_requires_bearer(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/billing/invoices")).status_code == 401


def test_billing_role_enforcement_and_superadmin_bypass() -> None:
    with pytest.raises(BillingError) as denied:
        require_owner(Identity(uuid4(), uuid4(), "Admin"))
    assert denied.value.status_code == 403
    assert require_owner(Identity(uuid4(), uuid4(), "Member", "SuperAdmin")).is_superadmin
