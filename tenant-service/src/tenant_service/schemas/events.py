from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AccountEventType(StrEnum):
    CREATED = "account.created"
    UPDATED = "account.updated"
    MEMBER_INVITED = "member.invited"
    MEMBER_JOINED = "member.joined"
    MEMBER_ROLE_UPDATED = "member.role_updated"
    MEMBER_REMOVED = "member.removed"


class AccountEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_type: AccountEventType
    account_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any]
