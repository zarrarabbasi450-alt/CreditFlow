from typing import Protocol

import httpx

from notification_service.core.errors import NotificationError


class SlackClientProtocol(Protocol):
    async def send(self, text: str) -> None: ...
    async def close(self) -> None: ...


class SlackWebhookClient:
    """Posts to a Slack Incoming Webhook — no OAuth app review needed. Used for
    internal ops alerts only (optional; the platform never sends customer email
    through this channel)."""

    def __init__(self, webhook_url: str, timeout_seconds: float) -> None:
        self.webhook_url = webhook_url
        self.client = httpx.AsyncClient(timeout=timeout_seconds)

    async def send(self, text: str) -> None:
        if not self.webhook_url:
            raise NotificationError(
                503, "SLACK_NOT_CONFIGURED", "SLACK_WEBHOOK_URL is not configured for this environment"
            )
        response = await self.client.post(self.webhook_url, json={"text": text})
        if response.status_code >= 400:
            raise NotificationError(
                502, "SLACK_SEND_FAILED", "Slack rejected the webhook", {"status_code": response.status_code}
            )

    async def close(self) -> None:
        await self.client.aclose()
