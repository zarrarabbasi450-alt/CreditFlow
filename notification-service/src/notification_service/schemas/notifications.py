from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Channel = Literal["email", "slack"]
DeliveryStatus = Literal["sent", "failed", "skipped"]
NotificationCategory = Literal["Publishing", "Credits", "Account"]
ReadStatus = Literal["Read", "Unread"]


class NotificationLogRead(BaseModel):
    id: UUID
    account_id: UUID | None
    user_id: UUID | None
    event_type: str
    channel: Channel
    recipient: str | None
    subject: str | None
    status: DeliveryStatus
    provider: str | None
    provider_message_id: str | None
    error: str | None
    correlation_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationItem(BaseModel):
    """Audit-log row reshaped to the workspace notifications feed contract.

    Field names here are camelCase on purpose: the frontend's `lib/api/notifications.ts`
    consumes this response directly with no snake_case-to-camelCase mapping layer,
    unlike most other API modules.
    """

    id: UUID
    accountId: UUID | None
    title: str
    detail: str
    category: NotificationCategory
    status: ReadStatus
    createdAt: datetime


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


class NotificationCollection(BaseModel):
    view: ProductView
    items: list[NotificationItem]
