"""Recordings router: upload audio, transcribe, digest, re-digest, retranscribe. IDOR-safe."""

import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import nh3
from fastapi import APIRouter, HTTPException, Request, UploadFile, status

from app.auth import CurrentUser, DbSession
from app.config import settings
from app.dependencies import get_page_or_404
from app.models import BulletPoint, Page, Recording
from app.schemas import RecordingResponse, WHISPER_LANGUAGES, WHISPER_MODELS
from app.services.buffer import BufferUnauthorizedError, create_idea, is_buffer_trigger, strip_buffer_trigger
from app.services.digest import digest_transcript, generate_idea_title
from app.services.transcription import transcribe, validate_audio_file

from app.limiter import limiter

logger = logging.getLogger("pointify.recordings")
router = APIRouter(prefix="/api/v1", tags=["recordings"])

AUDIO_DIR = Path("data/audio")


def _get_recording_or_404(recording_id: uuid.UUID, user_id: uuid.UUID, db) -> Recording:  # noqa: ANN001
    """Fetch a recording, verifying IDOR: the recording's page must belong to the user."""
    recording = (
        db.query(Recording)
        .join(Page, Recording.page_id == Page.id)
        .filter(Recording.id == recording_id, Page.user_id == user_id)
        .first()
    )
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Recording not found", "error_code": "RECORDING_NOT_FOUND"},
        )
    return recording


@router.post(
    "/pages/{page_id}/recordings",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def upload_recording(
    request: Request,
    page_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile,
    whisper_model: str = "medium",
    whisper_language: str | None = None,
) -> Recording:
    """Upload an audio file, transcribe it, and generate bullet points."""
    if whisper_model not in WHISPER_MODELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": f"Invalid whisper model. Choose from: {', '.join(sorted(WHISPER_MODELS))}", "error_code": "INVALID_WHISPER_MODEL"},
        )

    # Resolve language: explicit override > user default. "auto" → None (Whisper detects).
    resolved_language_code = whisper_language or current_user.whisper_language
    if resolved_language_code not in WHISPER_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": f"Invalid language. Choose from: {', '.join(sorted(WHISPER_LANGUAGES))}", "error_code": "INVALID_LANGUAGE"},
        )
    transcribe_language = None if resolved_language_code == "auto" else resolved_language_code

    get_page_or_404(page_id, current_user.id, db)

    # Save file with a UUID name (no path traversal possible)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = AUDIO_DIR / f"{file_id}.audio"

    try:
        content = await file.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={"detail": f"File too large (max {settings.max_upload_mb}MB)", "error_code": "FILE_TOO_LARGE"},
            )
        file_path.write_bytes(content)

        # Validate file (size, MIME magic bytes, duration)
        try:
            validate_audio_file(file_path)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"detail": str(exc), "error_code": "INVALID_AUDIO_FILE"},
            ) from exc

        # Transcribe
        try:
            transcript = transcribe(file_path, model_name=whisper_model, language=transcribe_language)
        except Exception as exc:
            logger.exception("Transcription failed", extra={"error": str(exc)})
            transcript = ""

        # Sanitize transcript before storing (belt-and-suspenders)
        transcript = nh3.clean(transcript, tags=set())

        # Persist recording
        today = datetime.now(timezone.utc).date()
        recording = Recording(
            page_id=page_id,
            recorded_date=today,
            audio_path=str(file_path),
            transcript=transcript,
            whisper_model=whisper_model,
            whisper_language=resolved_language_code,
        )
        db.add(recording)
        db.commit()
        db.refresh(recording)

        # Generate bullet points asynchronously
        if transcript:
            bullets = await digest_transcript(transcript)
            created_bullets: list[BulletPoint] = []
            for i, text in enumerate(bullets):
                bp = BulletPoint(
                    recording_id=recording.id,
                    page_id=page_id,
                    day=today,
                    text=nh3.clean(text, tags=set()),
                    sort_order=i,
                )
                db.add(bp)
                created_bullets.append(bp)
            db.commit()

            # Best-effort: send bullets containing Buffer trigger phrase to Buffer Ideas
            if settings.buffer_enabled:
                for bp in created_bullets:
                    if not is_buffer_trigger(bp.text):
                        continue
                    idea_text = strip_buffer_trigger(bp.text)
                    if not idea_text:
                        continue
                    try:
                        idea_title = await generate_idea_title(idea_text)
                    except Exception as exc:
                        logger.warning("Title generation failed during auto-send", extra={"error": str(exc)})
                        idea_title = None
                    try:
                        idea_id = await create_idea(idea_text, title=idea_title)
                        if idea_id:
                            bp.buffer_idea_id = idea_id
                    except BufferUnauthorizedError as exc:
                        logger.warning("Buffer unauthorized during auto-send", extra={"error": str(exc)})
                        break  # all bullets will fail with same bad token, stop early
                    except Exception as exc:
                        logger.warning("Buffer auto-send failed", extra={"error": str(exc)})
                db.commit()

        logger.info(
            "Recording processed",
            extra={"user_id": current_user.id, "recording_id": recording.id, "model": whisper_model},
        )
        return recording

    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        logger.exception("Unexpected error processing recording", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to process recording", "error_code": "PROCESSING_ERROR"},
        ) from exc


@router.post("/recordings/{recording_id}/redigest", response_model=RecordingResponse)
@limiter.limit("3/minute")
async def redigest_recording(
    request: Request,
    recording_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Recording:
    """Re-run LLM digestion on an existing recording's transcript."""
    recording = _get_recording_or_404(recording_id, current_user.id, db)

    if not recording.transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "No transcript available to re-digest", "error_code": "NO_TRANSCRIPT"},
        )

    # Delete existing bullets from this recording
    db.query(BulletPoint).filter(BulletPoint.recording_id == recording_id).delete()
    db.commit()

    bullets = await digest_transcript(recording.transcript)
    today = recording.recorded_date
    for i, text in enumerate(bullets):
        bp = BulletPoint(
            recording_id=recording.id,
            page_id=recording.page_id,
            day=today,
            text=nh3.clean(text, tags=set()),
            sort_order=i,
        )
        db.add(bp)
    db.commit()
    db.refresh(recording)
    logger.info("Recording re-digested", extra={"recording_id": recording_id, "user_id": current_user.id})
    return recording


@router.post("/recordings/{recording_id}/retranscribe", response_model=RecordingResponse)
@limiter.limit("3/minute")
async def retranscribe_recording(
    request: Request,
    recording_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> Recording:
    """Re-run Whisper transcription on the stored audio file, then re-digest into bullet points."""
    recording = _get_recording_or_404(recording_id, current_user.id, db)

    audio_path = Path(recording.audio_path)
    if not audio_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Audio file no longer on disk — cannot retranscribe", "error_code": "AUDIO_FILE_MISSING"},
        )

    retranscribe_language = None if recording.whisper_language == "auto" else recording.whisper_language
    try:
        transcript = transcribe(audio_path, model_name=recording.whisper_model, language=retranscribe_language)
    except Exception as exc:
        logger.exception("Retranscription failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Transcription failed", "error_code": "TRANSCRIPTION_ERROR"},
        ) from exc

    recording.transcript = nh3.clean(transcript, tags=set())
    db.commit()

    db.query(BulletPoint).filter(BulletPoint.recording_id == recording_id).delete()
    db.commit()

    if recording.transcript:
        bullets = await digest_transcript(recording.transcript)
        for i, text in enumerate(bullets):
            bp = BulletPoint(
                recording_id=recording.id,
                page_id=recording.page_id,
                day=recording.recorded_date,
                text=nh3.clean(text, tags=set()),
                sort_order=i,
            )
            db.add(bp)
        db.commit()

    db.refresh(recording)
    logger.info("Recording retranscribed", extra={"recording_id": recording_id, "user_id": current_user.id})
    return recording


@router.delete("/recordings/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recording(recording_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Archive a recording (soft-delete): sets archived_at, keeps the audio file and bullet points."""
    recording = _get_recording_or_404(recording_id, current_user.id, db)
    recording.archived_at = datetime.now(timezone.utc)
    db.commit()


@router.get(
    "/pages/{page_id}/recordings",
    response_model=list[RecordingResponse],
)
async def list_recordings(page_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> list[Recording]:
    get_page_or_404(page_id, current_user.id, db)
    return (
        db.query(Recording)
        .filter(Recording.page_id == page_id, Recording.archived_at.is_(None))
        .order_by(Recording.recorded_date.desc(), Recording.created_at.desc())
        .all()
    )
