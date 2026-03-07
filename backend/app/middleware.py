"""
Security headers middleware, request ID tracking, structured JSON logging.

SECURITY IS TOP PRIORITY. NEVER SACRIFICE.
"""

import json
import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns a unique X-Request-ID to every request for tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to every response.
    HSTS is included but only meaningful over HTTPS.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "  # unsafe-inline needed for Tailwind JIT
            "img-src 'self' data:; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Permissions-Policy"] = (
            "microphone=(self), camera=(), geolocation=()"
        )
        return response


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with structured JSON fields. Never logs sensitive data."""

    _SENSITIVE_PATHS = {"/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/auth/change-password"}

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("pointify.access")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", "-")
        user_id: int | None = None

        response = await call_next(request)

        # Attempt to extract user_id from request state (set by auth dep)
        user_id = getattr(request.state, "user_id", None)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log_record = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "ip": request.client.host if request.client else None,
        }
        self.logger.info(json.dumps(log_record))
        return response


def setup_logging(log_level: str) -> None:
    """Configure structured JSON logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_obj = {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
            # Include any extra fields passed to the logger
            for key, val in record.__dict__.items():
                if key not in (
                    "args", "asctime", "created", "exc_info", "exc_text",
                    "filename", "funcName", "id", "levelname", "levelno",
                    "lineno", "module", "msecs", "message", "msg", "name",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "thread", "threadName", "taskName",
                ):
                    log_obj[key] = val
            if record.exc_info:
                log_obj["exc"] = self.formatException(record.exc_info)
            return json.dumps(log_obj, default=str)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.handlers = [handler]

    # Quiet noisy third-party loggers
    for lib in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(lib).setLevel(logging.WARNING)
