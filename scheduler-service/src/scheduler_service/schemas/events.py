from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    occurred_at: datetime
    correlation_id: str | None = None
    payload: dict[str, Any]


class ContentScheduledPayload(BaseModel):
    scheduled_post_id: UUID
    account_id: UUID
    content_id: UUID
    publish_at: datetime
    title: str
