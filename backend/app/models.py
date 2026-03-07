import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="user")
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    whisper_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pages: Mapped[list["Page"]] = relationship("Page", back_populates="owner", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship("User", back_populates="pages")
    recordings: Mapped[list["Recording"]] = relationship(
        "Recording", back_populates="page", cascade="all, delete-orphan"
    )
    bullet_points: Mapped[list["BulletPoint"]] = relationship(
        "BulletPoint", back_populates="page", cascade="all, delete-orphan"
    )


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    page_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    audio_path: Mapped[str] = mapped_column(String(512), nullable=False)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    whisper_model: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    whisper_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    page: Mapped["Page"] = relationship("Page", back_populates="recordings")
    bullet_points: Mapped[list["BulletPoint"]] = relationship(
        "BulletPoint", back_populates="recording", cascade="all, delete-orphan"
    )


class BulletPoint(Base):
    __tablename__ = "bullet_points"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    recording_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("recordings.id", ondelete="SET NULL"), nullable=True
    )
    page_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    recording: Mapped["Recording | None"] = relationship("Recording", back_populates="bullet_points")
    page: Mapped["Page"] = relationship("Page", back_populates="bullet_points")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_whisper_model: Mapped[str] = mapped_column(String(20), default="base")
    ollama_model: Mapped[str] = mapped_column(String(50), default="gpt-oss:20b")
