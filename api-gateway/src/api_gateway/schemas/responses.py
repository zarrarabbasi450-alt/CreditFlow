from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


class DashboardResponse(BaseModel):
    success: bool = True
    data: dict[str, Any]
    degraded_services: list[str] = Field(default_factory=list)
    request_id: str
    correlation_id: str


class AdminMetric(BaseModel):
    label: str
    value: str
    change: str


class AdminActivity(BaseModel):
    title: str
    detail: str
    status: str


class AdminView(BaseModel):
    title: str = "Operations"
    eyebrow: str = "Platform administration"
    description: str = "Monitor CreditFlow services and manage global access."
    action: str = "Review users"
    metrics: list[AdminMetric]
    rows: list[AdminActivity]


class ServiceHealth(BaseModel):
    service: str
    status: str
    uptime: float
    latencyP95Ms: int
    detail: str


class AdminOverviewResponse(BaseModel):
    view: AdminView
    health: list[ServiceHealth]
    audit: list[dict[str, Any]] = Field(default_factory=list)
    flags: list[dict[str, Any]] = Field(default_factory=list)
