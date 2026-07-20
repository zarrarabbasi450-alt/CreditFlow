from typing import Protocol
from uuid import UUID

import httpx

from credits_service.core.errors import CreditsError


class BillingProtocol(Protocol):
    async def create_escrow(
        self, token: str, listing_id: UUID, seller_account_id: UUID, amount: int
    ) -> tuple[str, str | None, str]: ...
    async def capture_escrow(self, token: str, payment_intent_id: str) -> str: ...


class BillingClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def create_escrow(
        self, token: str, listing_id: UUID, seller_account_id: UUID, amount: int
    ) -> tuple[str, str | None, str]:
        payload = {
            "listing_id": str(listing_id),
            "seller_account_id": str(seller_account_id),
            "amount": amount,
            "currency": "usd",
        }
        data = await self._request("POST", "/api/v1/billing/escrows", token, payload)
        secret = data.get("client_secret")
        return str(data["payment_intent_id"]), str(secret) if secret else None, str(data["status"])

    async def capture_escrow(self, token: str, payment_intent_id: str) -> str:
        data = await self._request(
            "POST", f"/api/v1/billing/escrows/{payment_intent_id}/capture", token, None
        )
        return str(data["status"])

    async def _request(
        self, method: str, path: str, token: str, payload: dict[str, object] | None
    ) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request(
                    method,
                    self.base_url + path,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise CreditsError(503, "BILLING_UNAVAILABLE", "Billing Service is unavailable") from exc
        if response.status_code >= 400:
            raise CreditsError(502, "BILLING_REJECTED", "Billing Service rejected the payment")
        return dict(response.json())
