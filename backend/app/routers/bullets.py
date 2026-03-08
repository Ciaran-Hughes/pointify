"""Bullets router: CRUD for bullet points with full IDOR prevention."""

import logging
import uuid
from datetime import date, datetime, timezone

import nh3
from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser, DbSession
from app.dependencies import get_page_or_404
from app.models import BulletPoint, Page, Recording
from app.schemas import BulletCreate, BulletResponse, BulletReorder, BulletUpdate, DayGroup, RecordingGroup

logger = logging.getLogger("pointify.bullets")
router = APIRouter(prefix="/api/v1", tags=["bullets"])


def _get_bullet_or_404(bullet_id: uuid.UUID, user_id: uuid.UUID, db) -> BulletPoint:  # noqa: ANN001
    """Fetch a bullet, verifying ownership via page -> user chain (IDOR prevention)."""
    bullet = (
        db.query(BulletPoint)
        .join(Page, BulletPoint.page_id == Page.id)
        .filter(BulletPoint.id == bullet_id, Page.user_id == user_id)
        .first()
    )
    if not bullet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Bullet not found", "error_code": "BULLET_NOT_FOUND"},
        )
    return bullet


@router.get("/pages/{page_id}/days", response_model=list[DayGroup])
async def get_page_by_days(
    page_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> list[DayGroup]:
    """Return bullets grouped by day then by recording (newest first). Orphan bullets listed separately."""
    get_page_or_404(page_id, current_user.id, db)

    # Fetch all non-archived recordings for this page, ordered by creation time within each day
    all_recordings = (
        db.query(Recording)
        .filter(Recording.page_id == page_id, Recording.archived_at.is_(None))
        .order_by(Recording.recorded_date.desc(), Recording.created_at.desc())
        .all()
    )
    recording_map: dict[uuid.UUID, Recording] = {rec.id: rec for rec in all_recordings}

    # Fetch all bullets, ordered by day desc then sort_order asc
    bullets = (
        db.query(BulletPoint)
        .filter(BulletPoint.page_id == page_id)
        .order_by(BulletPoint.day.desc(), BulletPoint.sort_order.asc())
        .all()
    )

    # Build per-day structure: { day -> { recording_id|None -> [bullets] } }
    days_recordings: dict[date, dict] = {}
    days_order: list[date] = []
    for bp in bullets:
        if bp.day not in days_recordings:
            days_recordings[bp.day] = {}
            days_order.append(bp.day)
        key = bp.recording_id
        days_recordings[bp.day].setdefault(key, []).append(bp)

    # Also ensure days that have recordings but no bullets appear
    for rec in all_recordings:
        if rec.recorded_date not in days_recordings:
            days_recordings[rec.recorded_date] = {}
            days_order.append(rec.recorded_date)

    # Deduplicate and sort days newest-first
    seen: set[date] = set()
    unique_days = []
    for d in days_order:
        if d not in seen:
            seen.add(d)
            unique_days.append(d)
    unique_days.sort(reverse=True)

    result = []
    for day in unique_days:
        bucket = days_recordings[day]

        # Build one RecordingGroup per non-archived recording that has bullets or exists for this day
        day_recordings = [rec for rec in all_recordings if rec.recorded_date == day]

        groups = []
        for rec in day_recordings:
            rec_bullets = bucket.get(rec.id, [])
            groups.append(RecordingGroup(recording=rec, bullets=rec_bullets))

        orphan_bullets = bucket.get(None, [])

        # Only include the day if it has at least one group or orphan bullet
        if groups or orphan_bullets:
            result.append(DayGroup(day=day, groups=groups, orphan_bullets=orphan_bullets))

    return result


@router.post("/pages/{page_id}/bullets", response_model=BulletResponse, status_code=status.HTTP_201_CREATED)
async def add_bullet(page_id: uuid.UUID, body: BulletCreate, current_user: CurrentUser, db: DbSession) -> BulletPoint:
    """Manually add a bullet point to a page for a given day."""
    get_page_or_404(page_id, current_user.id, db)

    # Find max sort_order for this day
    existing = (
        db.query(BulletPoint)
        .filter(BulletPoint.page_id == page_id, BulletPoint.day == body.day)
        .order_by(BulletPoint.sort_order.desc())
        .first()
    )
    sort_order = (existing.sort_order + 1) if existing else 0

    bp = BulletPoint(
        page_id=page_id,
        recording_id=None,
        day=body.day,
        text=nh3.clean(body.text, tags=set()),
        sort_order=sort_order,
    )
    db.add(bp)
    db.commit()
    db.refresh(bp)
    return bp


@router.patch("/bullets/{bullet_id}", response_model=BulletResponse)
async def update_bullet(bullet_id: uuid.UUID, body: BulletUpdate, current_user: CurrentUser, db: DbSession) -> BulletPoint:
    bullet = _get_bullet_or_404(bullet_id, current_user.id, db)
    bullet.text = nh3.clean(body.text, tags=set())
    db.commit()
    db.refresh(bullet)
    return bullet


@router.delete("/bullets/{bullet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bullet(bullet_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    bullet = _get_bullet_or_404(bullet_id, current_user.id, db)
    db.delete(bullet)
    db.commit()


@router.patch("/pages/{page_id}/bullets/reorder", response_model=list[BulletResponse])
async def reorder_bullets(page_id: uuid.UUID, body: BulletReorder, current_user: CurrentUser, db: DbSession) -> list[BulletPoint]:
    """Update sort_order for a list of bullet IDs (provided in desired order)."""
    get_page_or_404(page_id, current_user.id, db)

    bullets = []
    for order, bullet_id in enumerate(body.ordered_ids):
        bullet = (
            db.query(BulletPoint)
            .join(Page, BulletPoint.page_id == Page.id)
            .filter(BulletPoint.id == bullet_id, BulletPoint.page_id == page_id, Page.user_id == current_user.id)
            .first()
        )
        if not bullet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": f"Bullet {bullet_id} not found or not in this page", "error_code": "BULLET_NOT_FOUND"},
            )
        bullet.sort_order = order
        bullets.append(bullet)

    db.commit()
    for b in bullets:
        db.refresh(b)
    return bullets


@router.delete("/recordings/{recording_id}/day", status_code=status.HTTP_204_NO_CONTENT)
async def delete_day(recording_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Archive a recording (soft-delete): sets archived_at, keeps audio file and bullet points."""
    recording = (
        db.query(Recording)
        .join(Page, Recording.page_id == Page.id)
        .filter(Recording.id == recording_id, Page.user_id == current_user.id)
        .first()
    )
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Recording not found", "error_code": "RECORDING_NOT_FOUND"},
        )
    recording.archived_at = datetime.now(timezone.utc)
    db.commit()
