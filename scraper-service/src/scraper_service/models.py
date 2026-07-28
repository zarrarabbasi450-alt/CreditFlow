from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

JobType = Literal["url", "serp", "research"]
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


def utcnow() -> datetime:
    return datetime.now(UTC)


class ScraperJob(BaseModel):
    """Mongo document stored in the `scraper_jobs` collection."""

    id: UUID = Field(default_factory=uuid4)
    account_id: UUID
    created_by: UUID
    job_type: JobType
    target: str
    name: str
    max_pages: int = 1
    status: JobStatus = "queued"
    recurring: bool = False
    interval_hours: int | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    pages_processed: int = 0
    answer: str | None = None
    failure_reason: str | None = None
    attempts: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ScrapedDocument(BaseModel):
    """Mongo document stored in the `scraped_documents` collection (flexible schema:
    `data` varies per job type — SERP results, page metadata, fetch errors, etc.)."""

    id: UUID = Field(default_factory=uuid4)
    job_id: UUID
    account_id: UUID
    job_type: JobType
    source: str
    title: str | None = None
    text: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=utcnow)
