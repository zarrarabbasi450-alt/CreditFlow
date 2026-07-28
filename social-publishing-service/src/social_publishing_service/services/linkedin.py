from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from social_publishing_service.core.config import Settings
from social_publishing_service.core.errors import SocialPublishingError


@dataclass(frozen=True)
class LinkedInTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    refresh_expires_at: datetime | None
    scopes: str


@dataclass(frozen=True)
class LinkedInProfile:
    urn: str
    name: str
    email: str | None


@dataclass(frozen=True)
class LinkedInPublishResult:
    post_id: str
    post_url: str | None
    asset_urn: str | None = None


class LinkedInClientProtocol(Protocol):
    def authorization_url(self, state: str) -> str: ...
    async def exchange_code(self, code: str) -> LinkedInTokens: ...
    async def profile(self, access_token: str) -> LinkedInProfile: ...
    async def refresh(self, refresh_token: str) -> LinkedInTokens: ...
    async def publish(
        self, access_token: str, author_urn: str, caption: str, image_url: str | None
    ) -> LinkedInPublishResult: ...
    async def close(self) -> None: ...


class LinkedInClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30)

    def authorization_url(self, state: str) -> str:
        if not self.settings.linkedin_client_id:
            raise SocialPublishingError(503, "LINKEDIN_NOT_CONFIGURED", "LinkedIn client id is missing")
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.linkedin_client_id,
                "redirect_uri": self.settings.linkedin_redirect_uri,
                "scope": " ".join(self.settings.linkedin_scopes),
                "state": state,
            }
        )
        return f"https://www.linkedin.com/oauth/v2/authorization?{query}"

    async def exchange_code(self, code: str) -> LinkedInTokens:
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.linkedin_redirect_uri,
                "client_id": self.settings.linkedin_client_id,
                "client_secret": self.settings.linkedin_client_secret,
            }
        )

    async def refresh(self, refresh_token: str) -> LinkedInTokens:
        return await self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.settings.linkedin_client_id,
                "client_secret": self.settings.linkedin_client_secret,
            }
        )

    async def _token_request(self, data: dict[str, str]) -> LinkedInTokens:
        response = await self.client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise SocialPublishingError(502, "LINKEDIN_TOKEN_FAILED", "LinkedIn token exchange failed")
        payload = response.json()
        now = datetime.now(UTC)
        expires_in = int(payload.get("expires_in") or 0)
        refresh_expires_in = int(payload.get("refresh_token_expires_in") or 0)
        return LinkedInTokens(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload["refresh_token"]) if payload.get("refresh_token") else None,
            expires_at=now + timedelta(seconds=expires_in) if expires_in else None,
            refresh_expires_at=now + timedelta(seconds=refresh_expires_in) if refresh_expires_in else None,
            scopes=str(payload.get("scope") or ""),
        )

    async def profile(self, access_token: str) -> LinkedInProfile:
        response = await self.client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            raise SocialPublishingError(502, "LINKEDIN_PROFILE_FAILED", "Unable to load LinkedIn profile")
        payload = response.json()
        subject = str(payload["sub"])
        name = str(payload.get("name") or "LinkedIn member")
        return LinkedInProfile(urn=f"urn:li:person:{subject}", name=name, email=payload.get("email"))

    async def publish(
        self, access_token: str, author_urn: str, caption: str, image_url: str | None
    ) -> LinkedInPublishResult:
        asset_urn = await self._upload_image(access_token, author_urn, image_url) if image_url else None
        result = (
            await self._publish_ugc(access_token, author_urn, caption, asset_urn)
            if self.settings.linkedin_api_mode == "ugc"
            else await self._publish_rest(access_token, author_urn, caption, asset_urn)
        )
        return LinkedInPublishResult(post_id=result.post_id, post_url=result.post_url, asset_urn=asset_urn)

    async def _upload_image(self, access_token: str, author_urn: str, image_url: str | None) -> str | None:
        if not image_url:
            return None
        register = await self.client.post(
            "https://api.linkedin.com/rest/images?action=initializeUpload",
            json={"initializeUploadRequest": {"owner": author_urn}},
            headers=self._rest_headers(access_token),
        )
        if register.status_code >= 500 or register.status_code == 429:
            raise httpx.HTTPStatusError(
                "Transient LinkedIn image registration failure",
                request=register.request,
                response=register,
            )
        if register.status_code >= 400:
            raise SocialPublishingError(
                502, "LINKEDIN_IMAGE_REGISTER_FAILED", "LinkedIn image upload registration failed"
            )
        value = dict(register.json().get("value") or {})
        upload_url = str(value["uploadUrl"])
        image_urn = str(value["image"])
        image_response = await self.client.get(image_url)
        image_response.raise_for_status()
        upload = await self.client.put(upload_url, content=image_response.content)
        if upload.status_code >= 500 or upload.status_code == 429:
            raise httpx.HTTPStatusError(
                "Transient LinkedIn image upload failure",
                request=upload.request,
                response=upload,
            )
        if upload.status_code >= 400:
            raise SocialPublishingError(502, "LINKEDIN_IMAGE_UPLOAD_FAILED", "LinkedIn image upload failed")
        return image_urn

    async def _publish_rest(
        self, access_token: str, author_urn: str, caption: str, asset_urn: str | None
    ) -> LinkedInPublishResult:
        payload: dict[str, Any] = {
            "author": author_urn,
            "commentary": caption,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if asset_urn:
            payload["content"] = {"media": {"id": asset_urn}}
        response = await self.client.post(
            "https://api.linkedin.com/rest/posts", json=payload, headers=self._rest_headers(access_token)
        )
        if response.status_code >= 500 or response.status_code == 429:
            raise httpx.HTTPStatusError(
                "Transient LinkedIn publish failure", request=response.request, response=response
            )
        if response.status_code >= 400:
            raise SocialPublishingError(
                502, "LINKEDIN_PUBLISH_FAILED", "LinkedIn rejected the post", {"body": response.text[:500]}
            )
        post_id = response.headers.get("x-restli-id") or str(
            response.json().get("id") if response.content else ""
        )
        return LinkedInPublishResult(post_id=post_id, post_url=None)

    async def _publish_ugc(
        self, access_token: str, author_urn: str, caption: str, asset_urn: str | None
    ) -> LinkedInPublishResult:
        media = (
            [{"status": "READY", "media": asset_urn, "title": {"text": "CreditFlow post"}}]
            if asset_urn
            else []
        )
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption},
                    "shareMediaCategory": "IMAGE" if asset_urn else "NONE",
                    "media": media,
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        response = await self.client.post(
            "https://api.linkedin.com/v2/ugcPosts", json=payload, headers=self._ugc_headers(access_token)
        )
        if response.status_code >= 500 or response.status_code == 429:
            raise httpx.HTTPStatusError(
                "Transient LinkedIn publish failure", request=response.request, response=response
            )
        if response.status_code >= 400:
            raise SocialPublishingError(
                502, "LINKEDIN_PUBLISH_FAILED", "LinkedIn rejected the post", {"body": response.text[:500]}
            )
        return LinkedInPublishResult(post_id=response.headers.get("x-restli-id") or "", post_url=None)

    def _rest_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Linkedin-Version": self.settings.linkedin_api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _ugc_headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    async def close(self) -> None:
        await self.client.aclose()
