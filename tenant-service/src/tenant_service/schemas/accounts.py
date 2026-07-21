from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from tenant_service.models import AccountType, MemberRole


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    type: AccountType
    plan_tier: str = Field(default="free", min_length=1, max_length=32)
    seat_count: int = Field(default=1, ge=1)


class AccountUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: str
    type: AccountType
    plan_tier: str
    seat_count: int
    created_at: datetime
    updated_at: datetime


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    user_id: UUID
    role: MemberRole
    created_at: datetime
    updated_at: datetime


class RoleUpdate(BaseModel):
    role: MemberRole


class InviteCreate(BaseModel):
    email: EmailStr
    role: MemberRole = MemberRole.MEMBER


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    email: EmailStr
    role: MemberRole
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime
