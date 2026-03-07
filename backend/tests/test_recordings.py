"""Tests: recording upload, re-digest, deletion, IDOR."""

import uuid
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import BulletPoint, Page, Recording


class TestRecordingUpload:
    def _upload(self, client, headers, page_id, content=b"fake audio", model="base"):
        return client.post(
            f"/api/v1/pages/{page_id}/recordings",
            files={"file": ("test.webm", BytesIO(content), "audio/webm")},
            params={"whisper_model": model},
            headers=headers,
        )

    def test_upload_invalid_page(self, client, regular_user, user_headers):
        r = self._upload(client, user_headers, uuid.uuid4())
        assert r.status_code == 404

    def test_upload_invalid_whisper_model(self, client, regular_user, user_headers, user_page):
        r = self._upload(client, user_headers, user_page.id, model="invalid")
        assert r.status_code == 422

    def test_upload_rejects_oversized_file(self, client, regular_user, user_headers, user_page):
        big = b"\x00" * (51 * 1024 * 1024)
        r = self._upload(client, user_headers, user_page.id, content=big)
        assert r.status_code == 413

    def test_upload_cannot_access_other_users_page(self, client, second_user, second_user_headers, user_page):
        r = self._upload(client, second_user_headers, user_page.id)
        assert r.status_code == 404


class TestRedigest:
    def test_redigest_no_transcript(self, client, regular_user, user_headers, user_page, db):
        rec = Recording(
            page_id=user_page.id,
            recorded_date=date.today(),
            audio_path="data/audio/test.audio",
            transcript=None,
            whisper_model="base",
        )
        db.add(rec)
        db.commit()
        r = client.post(f"/api/v1/recordings/{rec.id}/redigest", headers=user_headers)
        assert r.status_code == 400
        assert r.json()["detail"]["error_code"] == "NO_TRANSCRIPT"

    def test_redigest_idor(self, client, second_user, user_headers, db):
        other_page = Page(user_id=second_user.id, name="Other")
        db.add(other_page)
        db.commit()
        rec = Recording(
            page_id=other_page.id,
            recorded_date=date.today(),
            audio_path="data/audio/test.audio",
            transcript="Some text.",
            whisper_model="base",
        )
        db.add(rec)
        db.commit()
        r = client.post(f"/api/v1/recordings/{rec.id}/redigest", headers=user_headers)
        assert r.status_code == 404


class TestDeleteRecording:
    def test_delete_recording_idor(self, client, second_user, user_headers, db):
        other_page = Page(user_id=second_user.id, name="Other")
        db.add(other_page)
        db.commit()
        rec = Recording(
            page_id=other_page.id,
            recorded_date=date.today(),
            audio_path="data/audio/test.audio",
            transcript="Text.",
            whisper_model="base",
        )
        db.add(rec)
        db.commit()
        r = client.delete(f"/api/v1/recordings/{rec.id}", headers=user_headers)
        assert r.status_code == 404


class TestRecordingLanguage:
    """Tests for per-recording whisper_language selection and user default fallback."""

    def _make_upload_mocks(self):
        mock_seg = MagicMock()
        mock_seg.text = "I want to go hiking."
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], mock_info)
        return mock_model

    def test_explicit_language_stored_on_recording(self, client, regular_user, user_headers, user_page, tmp_path):
        mock_model = self._make_upload_mocks()
        audio = tmp_path / "test.webm"
        audio.write_bytes(b"\x00" * 64)

        mock_kind = MagicMock()
        mock_kind.mime = "audio/webm"
        mock_audio_info = MagicMock()
        mock_audio_info.info.length = 3.0

        with (
            patch("app.services.transcription._get_model", return_value=mock_model),
            patch("filetype.guess", return_value=mock_kind),
            patch("mutagen.File", return_value=mock_audio_info),
            patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=[])),
        ):
            r = client.post(
                f"/api/v1/pages/{user_page.id}/recordings",
                files={"file": ("test.webm", audio.read_bytes(), "audio/webm")},
                params={"whisper_model": "base", "whisper_language": "fi"},
                headers=user_headers,
            )

        assert r.status_code == 201
        data = r.json()
        assert data["whisper_language"] == "fi"
        mock_model.transcribe.assert_called_once()
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("language") == "fi"

    def test_defaults_to_user_whisper_language(self, client, regular_user, user_headers, user_page, db, tmp_path):
        regular_user.whisper_language = "sv"
        db.commit()

        mock_model = self._make_upload_mocks()
        audio = tmp_path / "test.webm"
        audio.write_bytes(b"\x00" * 64)

        mock_kind = MagicMock()
        mock_kind.mime = "audio/webm"
        mock_audio_info = MagicMock()
        mock_audio_info.info.length = 3.0

        with (
            patch("app.services.transcription._get_model", return_value=mock_model),
            patch("filetype.guess", return_value=mock_kind),
            patch("mutagen.File", return_value=mock_audio_info),
            patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=[])),
        ):
            r = client.post(
                f"/api/v1/pages/{user_page.id}/recordings",
                files={"file": ("test.webm", audio.read_bytes(), "audio/webm")},
                params={"whisper_model": "base"},
                headers=user_headers,
            )

        assert r.status_code == 201
        assert r.json()["whisper_language"] == "sv"
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("language") == "sv"

    def test_auto_language_passes_none_to_transcribe(self, client, regular_user, user_headers, user_page, tmp_path):
        mock_model = self._make_upload_mocks()
        audio = tmp_path / "test.webm"
        audio.write_bytes(b"\x00" * 64)

        mock_kind = MagicMock()
        mock_kind.mime = "audio/webm"
        mock_audio_info = MagicMock()
        mock_audio_info.info.length = 3.0

        with (
            patch("app.services.transcription._get_model", return_value=mock_model),
            patch("filetype.guess", return_value=mock_kind),
            patch("mutagen.File", return_value=mock_audio_info),
            patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=[])),
        ):
            r = client.post(
                f"/api/v1/pages/{user_page.id}/recordings",
                files={"file": ("test.webm", audio.read_bytes(), "audio/webm")},
                params={"whisper_model": "base", "whisper_language": "auto"},
                headers=user_headers,
            )

        assert r.status_code == 201
        assert r.json()["whisper_language"] == "auto"
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("language") is None

    def test_retranscribe_uses_stored_language(self, client, regular_user, user_headers, user_page, db, tmp_path):
        audio = tmp_path / "test.webm"
        audio.write_bytes(b"\x00" * 64)

        rec = Recording(
            page_id=user_page.id,
            recorded_date=date.today(),
            audio_path=str(audio),
            transcript="Old transcript.",
            whisper_model="base",
            whisper_language="de",
        )
        db.add(rec)
        db.commit()

        mock_model = self._make_upload_mocks()
        mock_kind = MagicMock()
        mock_kind.mime = "audio/webm"
        mock_audio_info = MagicMock()
        mock_audio_info.info.length = 3.0

        with (
            patch("app.services.transcription._get_model", return_value=mock_model),
            patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=[])),
        ):
            r = client.post(f"/api/v1/recordings/{rec.id}/retranscribe", headers=user_headers)

        assert r.status_code == 200
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("language") == "de"

    def test_upload_invalid_language_returns_422(self, client, regular_user, user_headers, user_page, tmp_path):
        audio = tmp_path / "test.webm"
        audio.write_bytes(b"\x00" * 64)
        r = client.post(
            f"/api/v1/pages/{user_page.id}/recordings",
            files={"file": ("test.webm", audio.read_bytes(), "audio/webm")},
            params={"whisper_model": "base", "whisper_language": "zz"},
            headers=user_headers,
        )
        assert r.status_code == 422
