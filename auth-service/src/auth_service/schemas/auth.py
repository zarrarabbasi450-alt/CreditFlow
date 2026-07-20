import re
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class StrongPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not all((
            re.search(r"[A-Z]", value),
            re.search(r"[a-z]", value),
            re.search(r"\d", value),
            re.search(r"[^A-Za-z0-9]", value),
        )):
            raise ValueError("Password must include uppercase, lowercase, number, and special character")
        return value


class SignupRequest(StrongPasswordRequest):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=1)


class SwitchAccountRequest(BaseModel):
    accountId: UUID


class LogoutRequest(BaseModel):
    refreshToken: str = Field(min_length=1)


class TokenRequest(BaseModel):
    token: str = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(StrongPasswordRequest):
    token: str = Field(min_length=1)


class AuthUserResponse(BaseModel):
    id: UUID
    email: EmailStr
    accountId: UUID
    role: str
    accountRole: str
    platformRole: str | None = None


class AdminUserResponse(BaseModel):
    id: UUID
    email: EmailStr
    isActive: bool
    isEmailVerified: bool
    platformRole: str | None = None


class PlatformRoleUpdate(BaseModel):
    platformRole: Literal["SuperAdmin"] | None


class TokenType(StrEnum):
    BEARER = "bearer"


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: TokenType = TokenType.BEARER
    expiresIn: int


class LoginResponse(BaseModel):
    user: AuthUserResponse
    tokens: TokenResponse


class ResponseMeta(BaseModel):
    requestId: str
    correlationId: str


class SignupSuccessResponse(BaseModel):
    success: bool = True
    data: AuthUserResponse
    meta: ResponseMeta


class LoginSuccessResponse(BaseModel):
    success: bool = True
    data: LoginResponse
    meta: ResponseMeta


class MessageResponse(BaseModel):
    message: str


class MessageSuccessResponse(BaseModel):
    success: bool = True
    data: MessageResponse
    meta: ResponseMeta
