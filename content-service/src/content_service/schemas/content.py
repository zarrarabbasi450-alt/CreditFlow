from datetime import datetime
from typing import Literal
from uuid import UUID

import markdown
from pydantic import BaseModel, Field, computed_field

ContentStatus = Literal["draft", "approved", "published"]
ContentType = Literal["post", "article", "campaign_brief", "carousel"]

_MARKDOWN_EXTENSIONS = ["extra", "sane_lists", "nl2br"]


def render_markdown(body: str) -> str:
    return markdown.markdown(body, extensions=_MARKDOWN_EXTENSIONS)


class ContentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    body: str = Field(min_length=1)
    content_type: ContentType = "post"
    image_url: str | None = None
    image_asset_ref: str | None = None


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    body: str | None = Field(default=None, min_length=1)
    image_url: str | None = None
    image_asset_ref: str | None = None


class ContentRead(BaseModel):
    id: UUID
    account_id: UUID
    created_by: UUID
    title: str
    body: str
    content_type: str
    status: ContentStatus
    image_url: str | None
    image_asset_ref: str | None
    source_generation_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def body_html(self) -> str:
        return render_markdown(self.body)


class ContentVersionRead(BaseModel):
    id: UUID
    content_id: UUID
    version: int
    title: str
    body: str
    status: str
    image_url: str | None
    image_asset_ref: str | None
    edited_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def body_html(self) -> str:
        return render_markdown(self.body)


class ProductMetric(BaseModel):
    label: str
    value: str
    change: str


class ActivityRow(BaseModel):
    title: str
    detail: str
    status: str


class ProductView(BaseModel):
    title: str
    eyebrow: str
    description: str
    action: str
    metrics: list[ProductMetric]
    rows: list[ActivityRow | dict[str, str]]


class ContentCollection(BaseModel):
    view: ProductView
    items: list[ContentRead]
