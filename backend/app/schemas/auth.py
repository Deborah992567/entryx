"""Auth request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr = Field(description="User email address")
    password: str = Field(min_length=8, max_length=128, description="Account password (min 8 chars, must contain letter+digit)")
    name: str = Field(min_length=1, max_length=120, description="Display name")

    @field_validator("password")
    @classmethod
    def _password_has_letter(cls, v: str) -> str:
        if not any(ch.isalpha() for ch in v) or not any(ch.isdigit() for ch in v):
            raise ValueError("password must contain at least one letter and one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="Registered email address")
    password: str = Field(description="Account password")


class TokenPair(BaseModel):
    access_token: str = Field(description="Short-lived JWT access token")
    refresh_token: str = Field(description="Opaque refresh token for obtaining new access tokens")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(description="Access token TTL in seconds")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="Valid refresh token")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Unique user ID")
    email: str = Field(description="User email address")
    name: str = Field(description="Display name")
    role: str = Field(description="User role (user, admin)")
    preferences: dict = Field(description="User preferences (theme, language, etc)")


class AuthAuditMixin(BaseModel):
    ip: str = ""
    user_agent: str = ""


class LoginRequestAudit(LoginRequest, AuthAuditMixin):
    pass


class RegisterRequestAudit(RegisterRequest, AuthAuditMixin):
    pass


class RefreshTokenOut(BaseModel):
    expires_at: datetime
