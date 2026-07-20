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
