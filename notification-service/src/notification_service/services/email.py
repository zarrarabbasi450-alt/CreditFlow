import base64
import time
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

import httpx

from notification_service.core.errors import NotificationError


@dataclass(frozen=True)
class EmailSendResult:
    provider_message_id: str | None


class EmailClientProtocol(Protocol):
    async def send(self, to: str, subject: str, html: str, text: str) -> EmailSendResult: ...
    async def close(self) -> None: ...


class ResendEmailClient:
    """Thin client for Resend (https://resend.com) — free tier, no self-hosted SMTP."""

    def __init__(self, api_key: str, from_address: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.from_address = from_address
        self.client = httpx.AsyncClient(timeout=timeout_seconds)

    async def send(self, to: str, subject: str, html: str, text: str) -> EmailSendResult:
        if not self.api_key:
            raise NotificationError(
                503, "EMAIL_PROVIDER_NOT_CONFIGURED", "RESEND_API_KEY is not configured for this environment"
            )
        response = await self.client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "from": self.from_address,
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text,
            },
        )
        if response.status_code >= 400:
            raise NotificationError(
                502,
                "EMAIL_SEND_FAILED",
                "Resend rejected the email",
                {"status_code": response.status_code, "body": response.text[:500]},
            )
        return EmailSendResult(provider_message_id=response.json().get("id"))

    async def close(self) -> None:
        await self.client.aclose()


class GmailOAuthEmailClient:
    """Sends email via the Gmail API, authenticated as a real Gmail account through OAuth.

    Unlike Resend's sandbox mode, a verified Gmail account can send to any recipient without
    a custom domain — the trade-off is Gmail's own sending caps (~500/day on a personal account).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        sender_email: str,
        timeout_seconds: float,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.sender_email = sender_email
        self.client = httpx.AsyncClient(timeout=timeout_seconds)
        self._access_token: str | None = None
        self._access_token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._access_token_expires_at:
            return self._access_token
        response = await self.client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code >= 400:
            raise NotificationError(
                502,
                "EMAIL_SEND_FAILED",
                "Gmail OAuth token refresh failed",
                {"status_code": response.status_code, "body": response.text[:500]},
            )
        body = response.json()
        self._access_token = str(body["access_token"])
        self._access_token_expires_at = time.monotonic() + float(body.get("expires_in", 3600)) - 60
        return self._access_token

    async def send(self, to: str, subject: str, html: str, text: str) -> EmailSendResult:
        if not (self.client_id and self.client_secret and self.refresh_token):
            raise NotificationError(
                503, "EMAIL_PROVIDER_NOT_CONFIGURED", "Gmail OAuth credentials are not configured"
            )
        access_token = await self._get_access_token()
        message = MIMEMultipart("alternative")
        message["to"] = to
        message["from"] = self.sender_email
        message["subject"] = subject
        message.attach(MIMEText(text, "plain"))
        message.attach(MIMEText(html, "html"))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        response = await self.client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
        )
        if response.status_code >= 400:
            raise NotificationError(
                502,
                "EMAIL_SEND_FAILED",
                "Gmail API rejected the email",
                {"status_code": response.status_code, "body": response.text[:500]},
            )
        return EmailSendResult(provider_message_id=response.json().get("id"))

    async def close(self) -> None:
        await self.client.aclose()
