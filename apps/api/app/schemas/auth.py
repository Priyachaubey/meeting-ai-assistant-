from datetime import datetime

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    # Added for the redesigned registration form's "Company" field — maps to the auto-
    # created personal workspace's name. Optional and additive: omit it and registration
    # behaves exactly as before (workspace named after full_name/email).
    workspace_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    role: str
    audio_capture_mode: str
    preferred_language: str
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    audio_capture_mode: str | None = None
    preferred_language: str | None = None
