import logging
from typing import Protocol
from uuid import UUID

import httpx

from ai_generation_service.core.config import Settings

logger = logging.getLogger(__name__)


class CreditsClientProtocol(Protocol):
    async def consume(self, token: str, amount: int, reference_id: UUID, description: str) -> None: ...
    async def close(self) -> None: ...


class CreditsClient:
    """Debits the credits-service ledger for a completed generation.

    Best-effort and non-blocking: the generation has already run (and already
    cost real OpenRouter money) by the time this is called, so a failure here
    (e.g. insufficient credits, credits-service unavailable) is logged rather
    than raised — it must never undo or hide an already-delivered generation.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=10)

    async def consume(self, token: str, amount: int, reference_id: UUID, description: str) -> None:
        try:
            response = await self.client.post(
                f"{self.settings.credits_service_url}/api/v1/credits/consume",
                headers={"Authorization": f"Bearer {token}"},
                json={"amount": amount, "reference_id": str(reference_id), "description": description},
            )
            if response.status_code >= 400:
                logger.warning(
                    "credit_consumption_failed",
                    extra={"status_code": response.status_code, "body": response.text[:500]},
                )
        except httpx.HTTPError:
            logger.warning("credit_consumption_unreachable", exc_info=True)

    async def close(self) -> None:
        await self.client.aclose()


class InMemoryCreditsClient:
    def __init__(self) -> None:
        self.consumed: list[tuple[str, int, UUID, str]] = []

    async def consume(self, token: str, amount: int, reference_id: UUID, description: str) -> None:
        self.consumed.append((token, amount, reference_id, description))

    async def close(self) -> None:
        return None
