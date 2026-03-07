"""Pages router: CRUD for user-scoped pages with IDOR prevention."""

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import func

from app.auth import CurrentUser, DbSession
from app.dependencies import get_page_or_404
from app.models import Page
from app.schemas import PageCreate, PageResponse, PageUpdate, PaginatedPages

router = APIRouter(prefix="/api/v1/pages", tags=["pages"])


@router.get("", response_model=PaginatedPages)
async def list_pages(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> PaginatedPages:
    total = db.query(func.count(Page.id)).filter(Page.user_id == current_user.id).scalar() or 0
    pages = (
        db.query(Page)
        .filter(Page.user_id == current_user.id)
        .order_by(Page.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return PaginatedPages(items=pages, total=total, page=page, per_page=per_page)


@router.post("", response_model=PageResponse, status_code=status.HTTP_201_CREATED)
async def create_page(body: PageCreate, current_user: CurrentUser, db: DbSession) -> Page:
    new_page = Page(user_id=current_user.id, name=body.name)
    db.add(new_page)
    db.commit()
    db.refresh(new_page)
    return new_page


@router.get("/{page_id}", response_model=PageResponse)
async def get_page(page_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Page:
    return get_page_or_404(page_id, current_user.id, db)


@router.patch("/{page_id}", response_model=PageResponse)
async def update_page(page_id: uuid.UUID, body: PageUpdate, current_user: CurrentUser, db: DbSession) -> Page:
    page = get_page_or_404(page_id, current_user.id, db)
    page.name = body.name
    db.commit()
    db.refresh(page)
    return page


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(page_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    page = get_page_or_404(page_id, current_user.id, db)
    db.delete(page)
    db.commit()
