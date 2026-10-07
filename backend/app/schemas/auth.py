"""Pydantic request/response schemas for auth endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.security import normalize_email, validate_password_policy


class RegisterRequest(BaseModel):
    """Payload for ``POST /auth/register``."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)

    def normalized_email(self) -> str:
        """Lower-cased email used for storage and lookup."""
        return normalize_email(str(self.email))

    def checked_password(self) -> str:
        """Password after policy validation (raises ``PasswordPolicyError``)."""
        validate_password_policy(self.password)
        return self.password


class LoginRequest(BaseModel):
    """Payload for ``POST /auth/login``."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

    def normalized_email(self) -> str:
        """Lower-cased email used for lookup."""
        return normalize_email(str(self.email))


class UserOut(BaseModel):
    """Public representation of a user (never exposes password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    display_name: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class AuthResponse(BaseModel):
    """Login/registration response."""

    user: UserOut
    expires_at: datetime
