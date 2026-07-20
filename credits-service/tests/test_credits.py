from uuid import uuid4

from httpx import AsyncClient


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
