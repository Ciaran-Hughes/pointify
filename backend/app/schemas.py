import re
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Shared validators ────────────────────────────────────────────────────────

def _validate_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    return v


USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


def _validate_username(v: str) -> str:
    if not USERNAME_PATTERN.match(v):
        raise ValueError(
            "Username must be 3-30 characters and contain only letters, digits, and underscores"
        )
    return v.lower()


# ── Constants ────────────────────────────────────────────────────────────────

WHISPER_MODELS = {"tiny", "base", "small", "medium", "large-v3"}

# Maps ISO-639-1 code → display name. "auto" means let Whisper detect.
WHISPER_LANGUAGES: dict[str, str] = {
    "auto": "Auto-detect",
    "en": "English",
    "fi": "Finnish",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "ar": "Arabic",
}


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: Annotated[str, Field(min_length=8)]

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password(v)


# ── Users (Admin) ─────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: Annotated[str, Field(min_length=8)]
    role: str = "user"

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return _validate_username(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "user"):
            raise ValueError("Role must be 'admin' or 'user'")
        return v


class UserUpdate(BaseModel):
    username: str | None = None
    role: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_username(v)
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("admin", "user"):
            raise ValueError("Role must be 'admin' or 'user'")
        return v


class UserPreferencesUpdate(BaseModel):
    whisper_language: str

    @field_validator("whisper_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in WHISPER_LANGUAGES:
            raise ValueError(
                f"whisper_language must be one of: {', '.join(sorted(WHISPER_LANGUAGES))}"
            )
        return v


class AdminResetPassword(BaseModel):
    new_password: Annotated[str, Field(min_length=8)]

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    role: str
    must_change_password: bool
    is_active: bool
    whisper_language: str
    created_at: datetime
    disabled_at: datetime | None


# ── Pages ─────────────────────────────────────────────────────────────────────

class PageCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class PageUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)]

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class PaginatedPages(BaseModel):
    items: list[PageResponse]
    total: int
    page: int
    per_page: int


# ── Recordings ────────────────────────────────────────────────────────────────


class RecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_id: UUID
    recorded_date: date
    transcript: str | None
    whisper_model: str
    whisper_language: str
    created_at: datetime


# ── Bullet Points ─────────────────────────────────────────────────────────────

class BulletCreate(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    day: date

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class BulletUpdate(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class BulletReorder(BaseModel):
    ordered_ids: list[UUID]


class BulletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recording_id: UUID | None
    page_id: UUID
    day: date
    text: str
    sort_order: int
    created_at: datetime


class RecordingGroup(BaseModel):
    recording: RecordingResponse
    bullets: list[BulletResponse]


class DayGroup(BaseModel):
    day: date
    groups: list[RecordingGroup]
    orphan_bullets: list[BulletResponse]


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    db: bool
    ollama: bool


# ── Settings ──────────────────────────────────────────────────────────────────

class AppSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    default_whisper_model: str
    ollama_model: str


class AppSettingsUpdate(BaseModel):
    default_whisper_model: str | None = None
    ollama_model: str | None = None

    @field_validator("default_whisper_model")
    @classmethod
    def validate_whisper_model(cls, v: str | None) -> str | None:
        if v is not None and v not in WHISPER_MODELS:
            raise ValueError(f"Whisper model must be one of: {', '.join(sorted(WHISPER_MODELS))}")
        return v
