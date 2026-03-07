"""
Auth utilities: password hashing, JWT creation/validation,
refresh token management, account lockout, FastAPI dependencies.

SECURITY IS TOP PRIORITY. NEVER SACRIFICE.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import RefreshToken, User

logger = logging.getLogger(__name__)

# ── Password hashing ──────────────────────────────────────────────────────────
# Using bcrypt directly (passlib 1.7.4 is incompatible with bcrypt 4+/5+).


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── Account lockout (in-memory) ───────────────────────────────────────────────

_lockout_lock = Lock()
# Maps username -> (failure_count, lockout_until)
_failed_attempts: dict[str, tuple[int, datetime | None]] = {}

LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def check_lockout(username: str) -> None:
    """Raise 429 if the account is currently locked out."""
    with _lockout_lock:
        entry = _failed_attempts.get(username)
        if entry:
            count, locked_until = entry
            if locked_until and datetime.now(UTC) < locked_until:
                remaining = int((locked_until - datetime.now(UTC)).total_seconds() / 60) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "detail": f"Account locked. Try again in {remaining} minute(s).",
                        "error_code": "ACCOUNT_LOCKED",
                    },
                )
            elif locked_until and datetime.now(UTC) >= locked_until:
                # Lock expired — reset
                _failed_attempts.pop(username, None)


def record_failed_attempt(username: str) -> None:
    with _lockout_lock:
        entry = _failed_attempts.get(username, (0, None))
        count = entry[0] + 1
        locked_until = None
        if count >= LOCKOUT_MAX_ATTEMPTS:
            locked_until = datetime.now(UTC) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            logger.warning("Account locked due to repeated failures", extra={"username": username})
        _failed_attempts[username] = (count, locked_until)


def record_successful_login(username: str) -> None:
    with _lockout_lock:
        _failed_attempts.pop(username, None)


# ── JWT ───────────────────────────────────────────────────────────────────────

_jwt_secret: str | None = None


def _get_jwt_secret() -> str:
    global _jwt_secret  # noqa: PLW0603
    if _jwt_secret is None:
        _jwt_secret = settings.ensure_jwt_secret()
    return _jwt_secret


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "type"]},
        )
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Token expired", "error_code": "TOKEN_EXPIRED"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid token", "error_code": "INVALID_TOKEN"},
        )


# ── Refresh tokens ────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token(user_id: uuid.UUID, db: Session) -> str:
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw)
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    db_token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(db_token)
    db.commit()
    return raw


def validate_refresh_token(raw_token: str, db: Session) -> User:
    token_hash = _hash_token(raw_token)
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid refresh token", "error_code": "INVALID_REFRESH_TOKEN"},
        )
    if datetime.now(UTC) > db_token.expires_at.replace(tzinfo=UTC):
        db.delete(db_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Refresh token expired", "error_code": "REFRESH_TOKEN_EXPIRED"},
        )
    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user or not user.is_active:
        db.delete(db_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Account disabled", "error_code": "ACCOUNT_DISABLED"},
        )
    # Rotate: delete old token, caller will issue new one
    db.delete(db_token)
    db.commit()
    return user


def revoke_all_refresh_tokens(user_id: uuid.UUID, db: Session) -> None:
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    db.commit()


# ── FastAPI dependencies ──────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


def _get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Not authenticated", "error_code": "NOT_AUTHENTICATED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    user_id = uuid.UUID(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "User not found", "error_code": "USER_NOT_FOUND"},
        )
    # Always check is_active — catches users disabled after token issued
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Account disabled", "error_code": "ACCOUNT_DISABLED"},
        )
    return user


def get_current_user(
    user: Annotated[User, Depends(_get_current_user)],
) -> User:
    """Returns the current active user. Raises 401 if not authenticated."""
    return user


def get_current_user_allow_must_change(
    user: Annotated[User, Depends(_get_current_user)],
) -> User:
    """Like get_current_user but also allows through users who must change password."""
    return user


def require_password_changed(
    user: Annotated[User, Depends(_get_current_user)],
) -> User:
    """Raises 403 if user must change password first."""
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Password change required", "error_code": "PASSWORD_CHANGE_REQUIRED"},
        )
    return user


def require_admin(
    user: Annotated[User, Depends(require_password_changed)],
) -> User:
    """Raises 403 if user is not an admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Admin access required", "error_code": "ADMIN_REQUIRED"},
        )
    return user


# Convenience type aliases for route signatures
CurrentUser = Annotated[User, Depends(require_password_changed)]
CurrentUserAllowChange = Annotated[User, Depends(get_current_user_allow_must_change)]
AdminUser = Annotated[User, Depends(require_admin)]
DbSession = Annotated[Session, Depends(get_db)]
