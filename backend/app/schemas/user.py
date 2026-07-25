"""Authentication request and response schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    username: str | None = None
    full_name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_and_validate_credentials(cls, data):
        """Normalize identifiers and enforce bcrypt's UTF-8 byte boundary."""
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if isinstance(normalized.get("email"), str):
            normalized["email"] = normalized["email"].strip().lower()
        if isinstance(normalized.get("username"), str):
            normalized["username"] = normalized["username"].strip() or None
        password = normalized.get("password")
        if isinstance(password, str) and len(password.encode("utf-8")) > 72:
            raise ValueError("password must not exceed 72 UTF-8 bytes")
        return normalized


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
