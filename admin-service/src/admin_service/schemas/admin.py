from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

HealthStatus = Literal["Healthy", "Degraded", "Down"]


class SessionItem(BaseModel):
    jti: str
    user_id: UUID
    account_id: UUID
    account_role: str
    platform_role: str | None


class AccountSummary(BaseModel):
    account_id: UUID
    plan_tier: str | None
    seat_count: int | None
    member_count: int | None
    credit_balance: int | None
    usage_tokens: int | None
    usage_quota_tokens: int | None


class AuditEntry(BaseModel):
    """Timeline row. Field names are camelCase to match the frontend's existing
    `AuditEvent` type in `types/admin.ts`, which the admin console already renders
    without any snake_case-to-camelCase mapping layer."""

    id: UUID
    actorId: UUID | None
    accountId: UUID | None
    action: str
    resource: str
    createdAt: datetime
    correlationId: str | None

    model_config = {"from_attributes": True}


class ServiceHealthItem(BaseModel):
    service: str
    status: HealthStatus
    uptime: float
    latencyP95Ms: int
    detail: str


class FeatureFlagItem(BaseModel):
    key: str
    enabled: bool
    rolloutPercentage: int
    updatedAt: datetime


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
    rows: list[ActivityRow]


class AdminOverview(BaseModel):
    view: ProductView
    health: list[ServiceHealthItem]
    audit: list[AuditEntry]
    flags: list[FeatureFlagItem]
