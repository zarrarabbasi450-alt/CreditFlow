from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import httpx

from social_publishing_service.core.errors import SocialPublishingError


@dataclass(frozen=True)
class ContentSnapshot:
    id: UUID
    account_id: UUID
    title: str
    body: str
    status: str
    image_url: str | None = None
    image_asset_ref: str | None = None


class ContentClientProtocol(Protocol):
    async def get_content(self, content_id: UUID, bearer_token: str | None = None) -> ContentSnapshot: ...
    async def close(self) -> None: ...


class ContentClient:
    def __init__(self, base_url: str, internal_service_token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.internal_service_token = internal_service_token
        self.client = httpx.AsyncClient(timeout=10)

    async def get_content(self, content_id: UUID, bearer_token: str | None = None) -> ContentSnapshot:
        token = bearer_token or self.internal_service_token
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = await self.client.get(f"{self.base_url}/api/v1/content/{content_id}", headers=headers)
        if response.status_code >= 400:
            raise SocialPublishingError(
                502,
                "CONTENT_FETCH_FAILED",
                "Unable to fetch scheduled content",
                {"status_code": response.status_code},
            )
        data = dict(response.json())
        return self._parse(data)

    @staticmethod
    def _parse(data: dict[str, Any]) -> ContentSnapshot:
        return ContentSnapshot(
            id=UUID(str(data["id"])),
            account_id=UUID(str(data["account_id"] if "account_id" in data else data["accountId"])),
            title=str(data["title"]),
            body=str(data["body"]),
            status=str(data["status"]),
            image_url=str(data["image_url"] if "image_url" in data else data.get("imageUrl"))
            if data.get("image_url") or data.get("imageUrl")
            else None,
            image_asset_ref=str(
                data["image_asset_ref"] if "image_asset_ref" in data else data.get("imageAssetRef")
            )
            if data.get("image_asset_ref") or data.get("imageAssetRef")
            else None,
        )

    async def close(self) -> None:
        await self.client.aclose()
