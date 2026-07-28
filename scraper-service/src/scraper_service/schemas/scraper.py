from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import markdown
from pydantic import BaseModel, Field, computed_field, model_validator

JobType = Literal["url", "serp", "research"]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

_MARKDOWN_EXTENSIONS = ["extra", "sane_lists", "nl2br"]


def render_markdown(text: str) -> str:
    return str(markdown.markdown(text, extensions=_MARKDOWN_EXTENSIONS))


class ScraperJobCreate(BaseModel):
    job_type: JobType
    target: str = Field(min_length=1, max_length=2000)
    name: str = Field(min_length=2, max_length=180)
    max_pages: int = Field(default=1, ge=1, le=10)
    recurring: bool = False
    interval_hours: int | None = Field(default=None, ge=1, le=168)

    @model_validator(mode="after")
    def _recurring_requires_interval(self) -> ScraperJobCreate:
        if self.recurring and self.interval_hours is None:
            raise ValueError("interval_hours is required when recurring is true")
        return self

    @model_validator(mode="after")
    def _research_default_sources(self) -> ScraperJobCreate:
        if self.job_type == "research" and self.max_pages == 1:
            self.max_pages = 4
        return self


class ScraperJobRead(BaseModel):
    id: UUID
    account_id: UUID
    created_by: UUID
    job_type: JobType
    target: str
    name: str
    max_pages: int
    status: JobStatus
    recurring: bool
    interval_hours: int | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    pages_processed: int
    answer: str | None
    failure_reason: str | None
    attempts: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def answer_html(self) -> str:
        return render_markdown(self.answer) if self.answer else ""


class ScrapedDocumentRead(BaseModel):
    id: UUID
    job_id: UUID
    account_id: UUID
    job_type: JobType
    source: str
    title: str | None
    text: str
    data: dict[str, Any]
    fetched_at: datetime

    model_config = {"from_attributes": True}


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


class ScraperCollection(BaseModel):
    view: ProductView
    items: list[ScraperJobRead]
