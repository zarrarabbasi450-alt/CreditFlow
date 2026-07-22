from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ModelChoice = Literal["fast", "quality"]


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=12000)
    model: ModelChoice = "fast"
    generate_image: bool = False
    estimated_tokens: int | None = Field(default=None, ge=1, le=100000)


class GenerationStartResponse(BaseModel):
    job_id: UUID
    channel: str
    model: str
    status: str
    image_url: str | None = None


class GenerationJobResponse(BaseModel):
    id: UUID
    account_id: UUID
    user_id: UUID
    model: str
    status: str
    prompt: str
    response: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_microusd: int
    error_reason: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class PromptHistoryResponse(BaseModel):
    id: UUID
    job_id: UUID
    model: str
    prompt: str
    response: str
    total_tokens: int
    cost_microusd: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ImageRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)


class ImageResponse(BaseModel):
    id: UUID
    image_url: str
    status: str
