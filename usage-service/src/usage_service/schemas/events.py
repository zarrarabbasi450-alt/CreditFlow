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


class GenerationCompleted(BaseModel):
    event_id: UUID
    generation_id: UUID
    account_id: UUID
    user_id: UUID
    model: str = Field(min_length=1, max_length=128)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(gt=0)
    cost_microusd: int = Field(ge=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_token_total(self) -> GenerationCompleted:
        if self.prompt_tokens + self.completion_tokens != self.total_tokens:
            raise ValueError("total_tokens must equal prompt_tokens plus completion_tokens")
        return self
