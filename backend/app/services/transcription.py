"""
Transcription service using faster-whisper.
Models are cached in memory to avoid reloading on each request.
SECURITY: File size and duration validated before transcription.
"""

import logging
from pathlib import Path
from threading import Lock

import filetype
import mutagen
from faster_whisper import WhisperModel

from app.config import settings
from app.schemas import WHISPER_MODELS

logger = logging.getLogger("pointify.transcription")

ALLOWED_AUDIO_MIMETYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "video/webm",  # webm container with audio
}

_model_cache: dict[str, WhisperModel] = {}
_cache_lock = Lock()


def _get_model(model_name: str) -> WhisperModel:
    """Return a cached WhisperModel, loading it on first use."""
    if model_name not in WHISPER_MODELS:
        raise ValueError(f"Invalid model: {model_name}")
    with _cache_lock:
        if model_name not in _model_cache:
            logger.info("Loading Whisper model", extra={"model": model_name})
            _model_cache[model_name] = WhisperModel(model_name, device="cpu", compute_type="int8")
            logger.info("Whisper model loaded", extra={"model": model_name})
        return _model_cache[model_name]


def validate_audio_file(file_path: Path) -> None:
    """
    Validate:
    1. File size <= MAX_UPLOAD_MB
    2. MIME type is an allowed audio type (magic bytes check)
    3. Duration <= MAX_RECORDING_MINUTES
    Raises ValueError with descriptive message on failure.
    """
    # Size check
    size = file_path.stat().st_size
    if size > settings.max_upload_bytes:
        raise ValueError(f"File too large: {size / 1024 / 1024:.1f}MB (max {settings.max_upload_mb}MB)")

    # Magic bytes MIME check (not relying on Content-Type header)
    kind = filetype.guess(str(file_path))
    if kind is None or kind.mime not in ALLOWED_AUDIO_MIMETYPES:
        detected = kind.mime if kind else "unknown"
        raise ValueError(f"Invalid file type: {detected}. Only audio files are accepted.")

    # Duration check using mutagen
    try:
        audio_info = mutagen.File(str(file_path))
        if audio_info is not None and hasattr(audio_info, "info") and hasattr(audio_info.info, "length"):
            duration_sec = audio_info.info.length
            max_sec = settings.max_recording_minutes * 60
            if duration_sec > max_sec:
                raise ValueError(
                    f"Recording too long: {duration_sec:.0f}s "
                    f"(max {settings.max_recording_minutes} minutes)"
                )
    except mutagen.MutagenError:
        # If mutagen can't read the file, proceed — transcription will fail gracefully
        logger.warning("Could not determine audio duration", extra={"path": str(file_path)})


def transcribe(file_path: Path, model_name: str = "base", language: str | None = None) -> str:
    """
    Transcribe an audio file using faster-whisper.
    Returns the full transcript as a single string.

    Pass language=None to let Whisper auto-detect. Pass an ISO-639-1 code
    (e.g. "en", "fi") to skip detection and decode in that language.
    """
    model = _get_model(model_name)
    logger.info(
        "Starting transcription",
        extra={"model": model_name, "path": str(file_path), "language": language or "auto"},
    )
    segments, info = model.transcribe(str(file_path), beam_size=5, language=language)
    transcript = " ".join(seg.text.strip() for seg in segments).strip()
    logger.info(
        "Transcription complete",
        extra={"model": model_name, "language": info.language, "length": len(transcript)},
    )
    return transcript
