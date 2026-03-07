"""Admin router: user CRUD, system settings. Admin-only. Full audit logging."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func

from app.auth import AdminUser, DbSession, hash_password, revoke_all_refresh_tokens
from app.models import AppSettings, User
from app.schemas import (
    AdminResetPassword,
    AppSettingsResponse,
    AppSettingsUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)

logger = logging.getLogger("pointify.admin")
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _audit(admin: User, action: str, target_user_id: uuid.UUID | None = None, **extra: object) -> None:
    logger.info(
        "AUDIT",
        extra={
            "audit": True,
            "admin_id": admin.id,
            "action": action,
            "target_user_id": target_user_id,
            **extra,
        },
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
async def list_users(admin: AdminUser, db: DbSession) -> list[User]:
    return db.query(User).order_by(User.created_at).all()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, admin: AdminUser, db: DbSession) -> User:
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Username already exists", "error_code": "USERNAME_TAKEN"},
        )
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        must_change_password=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _audit(admin, "USER_CREATE", target_user_id=user.id, username=body.username, role=body.role)
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"detail": "User not found", "error_code": "USER_NOT_FOUND"})
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: uuid.UUID, body: UserUpdate, admin: AdminUser, db: DbSession) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"detail": "User not found", "error_code": "USER_NOT_FOUND"})

    # Prevent admin from demoting themselves if they are the only admin
    if body.role == "user" and user.id == admin.id:
        admin_count = db.query(func.count(User.id)).filter(User.role == "admin", User.is_active == True).scalar()  # noqa: E712
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Cannot demote the only admin", "error_code": "LAST_ADMIN"},
            )

    changes: dict = {}
    if body.username is not None:
        existing = db.query(User).filter(User.username == body.username, User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"detail": "Username already exists", "error_code": "USERNAME_TAKEN"},
            )
        changes["username"] = body.username
        user.username = body.username
    if body.role is not None:
        changes["role"] = body.role
        user.role = body.role

    db.commit()
    db.refresh(user)
    _audit(admin, "USER_UPDATE", target_user_id=user_id, changes=changes)
    return user


@router.post("/users/{user_id}/disable", response_model=UserResponse)
async def disable_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> User:
    """Soft-delete: disable account but preserve all data."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"detail": "User not found", "error_code": "USER_NOT_FOUND"})
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Cannot disable your own account", "error_code": "SELF_DISABLE"},
        )
    user.is_active = False
    user.disabled_at = datetime.now(UTC)
    db.commit()
    revoke_all_refresh_tokens(user_id, db)
    db.refresh(user)
    _audit(admin, "USER_DISABLE", target_user_id=user_id)
    return user


@router.post("/users/{user_id}/enable", response_model=UserResponse)
async def enable_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> User:
    """Re-enable a previously disabled user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"detail": "User not found", "error_code": "USER_NOT_FOUND"})
    user.is_active = True
    user.disabled_at = None
    db.commit()
    db.refresh(user)
    _audit(admin, "USER_ENABLE", target_user_id=user_id)
    return user


@router.post("/users/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(user_id: uuid.UUID, body: AdminResetPassword, admin: AdminUser, db: DbSession) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"detail": "User not found", "error_code": "USER_NOT_FOUND"})
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = True
    db.commit()
    revoke_all_refresh_tokens(user_id, db)
    db.refresh(user)
    _audit(admin, "USER_RESET_PASSWORD", target_user_id=user_id)
    return user


# ── App Settings ──────────────────────────────────────────────────────────────

@router.get("/settings", response_model=AppSettingsResponse)
async def get_settings(admin: AdminUser, db: DbSession) -> AppSettings:
    s = db.query(AppSettings).first()
    if not s:
        raise HTTPException(status_code=500, detail="Settings not initialised")
    return s


@router.patch("/settings", response_model=AppSettingsResponse)
async def update_settings(body: AppSettingsUpdate, admin: AdminUser, db: DbSession) -> AppSettings:
    s = db.query(AppSettings).first()
    if not s:
        raise HTTPException(status_code=500, detail="Settings not initialised")
    changes: dict = {}
    if body.default_whisper_model is not None:
        s.default_whisper_model = body.default_whisper_model
        changes["default_whisper_model"] = body.default_whisper_model
    if body.ollama_model is not None:
        s.ollama_model = body.ollama_model
        changes["ollama_model"] = body.ollama_model
    db.commit()
    db.refresh(s)
    _audit(admin, "SETTINGS_UPDATE", changes=changes)
    return s
