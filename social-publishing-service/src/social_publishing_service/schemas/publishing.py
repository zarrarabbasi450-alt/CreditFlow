from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProductMetric(BaseModel):
    label: str
    value: str
    change: str


class ProductView(BaseModel):
    title: str
    eyebrow: str
    description: str
    action: str
    metrics: list[ProductMetric] = []
    rows: list[dict[str, str]] = []


class SocialConnectionRead(BaseModel):
    id: UUID
    account_id: UUID
    provider: str
    profile_name: str
    profile_urn: str | None
    status: str
    connected_at: datetime | None


class PublishJobRead(BaseModel):
    id: UUID
    account_id: UUID
    content_id: UUID
    scheduled_post_id: UUID | None = None
    connection_id: UUID | None = None
    status: str
    caption: str
    image_url: str | None = None
    linkedin_post_id: str | None = None
    linkedin_post_url: str | None = None
    failure_reason: str | None = None
    attempts: int
    created_at: datetime
    published_at: datetime | None = None


class PublishingCollection(BaseModel):
    view: ProductView
    connections: list[SocialConnectionRead]
    jobs: list[PublishJobRead]


class ConnectResponse(BaseModel):
    authorization_url: str
    state: str


class DevLinkedInConnectionRequest(BaseModel):
    profile_name: str = Field(min_length=1, max_length=240)
    profile_url: str = Field(min_length=8, max_length=500)


class PublishContentRequest(BaseModel):
    content_id: UUID
    connection_id: UUID | None = None
    caption: str | None = Field(default=None, max_length=3000)


class ManualLinkedInPostRequest(BaseModel):
    connection_id: UUID | None = None
    caption: str = Field(min_length=1, max_length=3000)
    image_url: str | None = None
    image_asset_ref: str | None = None
