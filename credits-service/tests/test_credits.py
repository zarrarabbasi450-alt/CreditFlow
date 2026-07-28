from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from conftest import BillingStub, BusStub, DatabaseStub, IdentityStub
from credits_service.core.config import get_settings
from credits_service.main import create_app
from credits_service.models import Base, CreditLedger, LedgerType


async def test_operations_and_auth(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200
    assert (await client.get("/version")).status_code == 200
    assert (await client.get("/api/v1/credits/balance")).status_code == 401


async def test_balance_listing_and_purchase(
    client: AsyncClient, auth: dict[str, str], seller_auth: dict[str, str]
) -> None:
    assert (await client.get("/api/v1/credits/balance", headers=seller_auth)).json()["balance"] == 5000
    listing = await client.post(
        "/api/v1/credits/marketplace/listings",
        headers=seller_auth,
        json={"credits": 1000, "price_cents": 2500},
    )
    assert listing.status_code == 201
    listing_id = listing.json()["id"]
    purchase = await client.post(
        "/api/v1/credits/marketplace/purchases", headers=auth, json={"listing_id": listing_id}
    )
    assert purchase.status_code == 200 and purchase.json()["payment_intent_id"] == "pi_test"
    confirmed = await client.post(
        f"/api/v1/credits/marketplace/purchases/{listing_id}/confirm",
        headers=auth,
        json={"payment_intent_id": "pi_test"},
    )
    assert confirmed.status_code == 200
    assert (await client.get("/api/v1/credits/balance", headers=auth)).json()["balance"] == 1000
    assert len((await client.get("/api/v1/credits/transactions", headers=auth)).json()) == 1


async def test_listing_validation(client: AsyncClient, seller_auth: dict[str, str]) -> None:
    insufficient = await client.post(
        "/api/v1/credits/marketplace/listings",
        headers=seller_auth,
        json={"credits": 999999, "price_cents": 1},
    )
    assert insufficient.status_code == 409
    missing = await client.delete(f"/api/v1/credits/marketplace/listings/{uuid4()}", headers=seller_auth)
    assert missing.status_code == 404


async def test_credit_consumption_is_atomic_and_idempotent(
    client: AsyncClient, seller_auth: dict[str, str]
) -> None:
    reference_id = str(uuid4())
    payload = {"amount": 750, "reference_id": reference_id, "description": "AI generation usage"}
    first = await client.post("/api/v1/credits/consume", headers=seller_auth, json=payload)
    repeated = await client.post("/api/v1/credits/consume", headers=seller_auth, json=payload)
    assert first.status_code == 200 and first.json()["balance"] == 4250
    assert repeated.status_code == 200 and repeated.json()["balance"] == 4250

    insufficient = await client.post(
        "/api/v1/credits/consume",
        headers=seller_auth,
        json={"amount": 999999, "reference_id": str(uuid4()), "description": "too much"},
    )
    assert insufficient.status_code == 409


async def test_credit_purchase_event_grants_balance() -> None:
    account_id = uuid4()
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"credits": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(DatabaseStub(sessions), BusStub(), IdentityStub(), BillingStub())
    envelope = {
        "event_id": str(uuid4()),
        "event_type": "credits.purchased",
        "correlation_id": "c1",
        "payload": {
            "account_id": str(account_id),
            "credits": 500,
            "payment_intent_id": "pi_credits",
            "amount": 500,
            "currency": "usd",
        },
    }
    await app.state.credits.consume(envelope)
    await app.state.credits.consume(envelope)  # duplicate delivery must not double-grant
    assert (await app.state.credits.balance(account_id)) == 500
    await engine.dispose()


async def test_internal_balance_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "shared-secret")
    get_settings.cache_clear()
    account_id = uuid4()
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"credits": None}},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        session.add(
            CreditLedger(
                account_id=account_id,
                entry_type=LedgerType.GRANT,
                amount=250,
                description="seed",
                reference_type="test",
                reference_id="seed",
            )
        )
    app = create_app(DatabaseStub(sessions), BusStub(), IdentityStub(), BillingStub())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        unauthorized = await client.get(
            f"/api/v1/credits/internal/{account_id}/balance",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert unauthorized.status_code == 401
        response = await client.get(
            f"/api/v1/credits/internal/{account_id}/balance",
            headers={"Authorization": "Bearer shared-secret"},
        )
        assert response.status_code == 200
        assert response.json() == {"account_id": str(account_id), "balance": 250}
    await engine.dispose()
    get_settings.cache_clear()
