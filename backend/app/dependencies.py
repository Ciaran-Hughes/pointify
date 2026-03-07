"""Shared FastAPI dependencies."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Page


def get_page_or_404(page_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> Page:
    """Fetch a page, verifying it belongs to the requesting user (IDOR prevention)."""
    page = db.query(Page).filter(Page.id == page_id, Page.user_id == user_id).first()
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Page not found", "error_code": "PAGE_NOT_FOUND"},
        )
    return page
