from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuotaCheckRequest(BaseModel):
    estimated_tokens: int = Field(gt=0)


class QuotaCheckResponse(BaseModel):
    allowed: bool
    tokens_used: int
    tokens_reserved: int
    quota_tokens: int
    remaining_tokens: int
    period: str


class ModelUsage(BaseModel):
    model: str
    tokens: int
    cost_microusd: int
    generations: int


class DailyUsage(BaseModel):
    day: str
    tokens: int
    cost_microusd: int
    generations: int


class UsageSummary(BaseModel):
    account_id: UUID
    period_start: datetime
    period_end: datetime
    tokens_used: int
    cost_microusd: int
    quota_tokens: int
    remaining_tokens: int
    quota_percentage: float
    generations: int
    by_model: list[ModelUsage]
    daily: list[DailyUsage]


class UsageLedgerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    generation_id: UUID
    account_id: UUID
    user_id: UUID
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_microusd: int
    created_at: datetime
