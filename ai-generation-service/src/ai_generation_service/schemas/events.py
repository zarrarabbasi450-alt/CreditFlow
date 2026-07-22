from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str
    payload: dict[str, Any]


class GenerationCompletedPayload(BaseModel):
    generation_id: UUID
    account_id: UUID
    user_id: UUID
    model: str
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(gt=0)
    cost_microusd: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> GenerationCompletedPayload:
        if self.prompt_tokens + self.completion_tokens != self.total_tokens:
            raise ValueError("total_tokens must equal prompt_tokens plus completion_tokens")
        return self


class GenerationFailedPayload(BaseModel):
    generation_id: UUID
    account_id: UUID
    user_id: UUID
    model: str
    reason: str
