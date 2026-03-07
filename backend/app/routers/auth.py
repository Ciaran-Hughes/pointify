"""Auth router: login, refresh, logout, change-password."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.auth import (
    AdminUser,
    CurrentUser,
    CurrentUserAllowChange,
    DbSession,
    check_lockout,
    create_access_token,
    create_refresh_token,
    hash_password,
    record_failed_attempt,
    record_successful_login,
    revoke_all_refresh_tokens,
    validate_refresh_token,
    verify_password,
)
from app.models import User
from app.schemas import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserPreferencesUpdate,
    UserResponse,
)

from app.limiter import limiter

logger = logging.getLogger("pointify.auth")
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: DbSession) -> TokenResponse:
    """Authenticate a user and return access + refresh tokens."""
    username = body.username.lower().strip()

    check_lockout(username)

    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(body.password, user.password_hash):
        record_failed_attempt(username)
        logger.warning("Failed login attempt", extra={"username": username})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid username or password", "error_code": "INVALID_CREDENTIALS"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Account disabled", "error_code": "ACCOUNT_DISABLED"},
        )

    record_successful_login(username)
    logger.info("User logged in", extra={"user_id": user.id})

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, db)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        must_change_password=user.must_change_password,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(body: RefreshRequest, db: DbSession) -> AccessTokenResponse:
    """Exchange a valid refresh token for a new access token (token rotation)."""
    user = validate_refresh_token(body.refresh_token, db)
    # Rotation: old token deleted by validate_refresh_token, issue new pair
    new_refresh_token = create_refresh_token(user.id, db)
    access_token = create_access_token(user.id, user.role)
    return AccessTokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUserAllowChange, db: DbSession) -> None:
    """Revoke all refresh tokens for the current user."""
    revoke_all_refresh_tokens(current_user.id, db)
    logger.info("User logged out", extra={"user_id": current_user.id})


@router.post("/change-password", response_model=UserResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUserAllowChange,
    db: DbSession,
) -> User:
    """Change the current user's password. Required on first login for admin."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Current password is incorrect", "error_code": "WRONG_CURRENT_PASSWORD"},
        )
    current_user.password_hash = hash_password(body.new_password)
    current_user.must_change_password = False
    db.commit()
    db.refresh(current_user)
    # Revoke all refresh tokens on password change (force re-login everywhere)
    revoke_all_refresh_tokens(current_user.id, db)
    logger.info("Password changed", extra={"user_id": current_user.id})
    return current_user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserAllowChange) -> User:
    """Return the currently authenticated user's profile."""
    return current_user


@router.patch("/me/preferences", response_model=UserResponse)
async def update_preferences(
    body: UserPreferencesUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> User:
    """Update the current user's transcription preferences."""
    current_user.whisper_language = body.whisper_language
    db.commit()
    db.refresh(current_user)
    logger.info("User preferences updated", extra={"user_id": current_user.id, "whisper_language": body.whisper_language})
    return current_user
