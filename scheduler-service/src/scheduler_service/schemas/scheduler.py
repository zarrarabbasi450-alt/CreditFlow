from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


class ScheduleCreate(BaseModel):
    content_id: UUID
    title: str = Field(min_length=1, max_length=180)
    publish_at: datetime
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid timezone") from exc
        return value


class ScheduleUpdate(BaseModel):
    publish_at: datetime
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid timezone") from exc
        return value


class ScheduledPostResponse(BaseModel):
    id: UUID
    account_id: UUID
    content_id: UUID
    title: str
    status: str
    publish_at: datetime
    publish_at_local: datetime
    timezone: str
    fired_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CalendarResponse(BaseModel):
    items: list[ScheduledPostResponse]
    timezone: str
    range_start: datetime
    range_end: datetime


class SchedulerSummary(BaseModel):
    scheduled_count: int
    due_count: int
    next_publish_at: datetime | None
