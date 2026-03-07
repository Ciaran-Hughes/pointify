"""
Pointify FastAPI application entry point.

SECURITY IS TOP PRIORITY. NEVER SACRIFICE.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.auth import hash_password
from app.config import settings
from sqlalchemy import text

from app.database import SessionLocal, engine, init_db
from app.limiter import limiter
from app.middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    StructuredLoggingMiddleware,
    setup_logging,
)
from app.models import AppSettings, User
from app.routers import admin, auth, bullets, pages, recordings

logger = logging.getLogger("pointify.main")


# ── Admin bootstrap ───────────────────────────────────────────────────────────

def _bootstrap_admin() -> None:
    """Create default admin user and app settings on first run."""
    db = SessionLocal()
    try:
        if not db.query(User).first():
            admin_user = User(
                username="admin",
                password_hash=hash_password("admin"),
                role="admin",
                must_change_password=True,
                is_active=True,
            )
            db.add(admin_user)
            logger.warning(
                "Created default admin user (admin/admin). "
                "CHANGE THIS PASSWORD IMMEDIATELY on first login."
            )

        if not db.query(AppSettings).first():
            db.add(AppSettings(
                default_whisper_model="medium",
                ollama_model=settings.ollama_model,
            ))

        db.commit()
    finally:
        db.close()


# ── Schema migrations (no Alembic) ────────────────────────────────────────────

def _migrate_db() -> None:
    """Apply additive schema changes to existing DBs that predate new columns.

    Checks PRAGMA table_info before running ALTER TABLE so it is safe to
    re-run on every startup — a no-op if columns already exist.
    """
    columns_to_add = [
        ("users", "whisper_language", "VARCHAR(10) NOT NULL DEFAULT 'en'"),
        ("recordings", "whisper_language", "VARCHAR(10) NOT NULL DEFAULT 'en'"),
    ]
    with engine.connect() as conn:
        for table, col, definition in columns_to_add:
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {definition}"))
        conn.commit()


# ── App lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging(settings.log_level)
    settings.ensure_jwt_secret()
    init_db()
    _migrate_db()
    _bootstrap_admin()
    logger.info("Pointify API started", extra={"ollama_url": settings.ollama_url})
    yield
    logger.info("Pointify API shutting down")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Pointify API",
    version="1.0.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — restrictive, no wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Total-Count"],
)

# Custom middleware (order matters: outermost runs first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(pages.router)
app.include_router(recordings.router)
app.include_router(bullets.router)


# ── Global error handlers ─────────────────────────────────────────────────────

@app.exception_handler(ValidationError)
async def validation_error_handler(_request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "error_code": "VALIDATION_ERROR"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "-")
    logger.exception("Unhandled exception", extra={"request_id": request_id, "error": str(exc)})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred", "error_code": "INTERNAL_ERROR", "request_id": request_id},
    )


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["health"])
async def health_check() -> dict:
    """Check DB and Ollama connectivity."""
    db_ok = False
    ollama_ok = False

    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_url}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "ollama": ollama_ok,
    }
