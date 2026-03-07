"""Tests: transcription validation (MIME, size, duration). Whisper mocked."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.schemas import WHISPER_MODELS
from app.services.transcription import WHISPER_MODELS as TRANSCRIPTION_WHISPER_MODELS
from app.services.transcription import validate_audio_file


class TestWhisperModelsConstant:
    def test_single_source_of_truth(self):
        """transcription.py must import WHISPER_MODELS from schemas, not define its own."""
        assert TRANSCRIPTION_WHISPER_MODELS is WHISPER_MODELS, (
            "transcription.py must re-export WHISPER_MODELS from app.schemas, "
            "not define a separate constant"
        )


class TestFileValidation:
    def test_rejects_oversized_file(self, tmp_path):
        big_file = tmp_path / "big.audio"
        big_file.write_bytes(b"\x00" * (51 * 1024 * 1024))
        with pytest.raises(ValueError, match="too large"):
            validate_audio_file(big_file)

    def test_rejects_non_audio_file(self, tmp_path):
        txt_file = tmp_path / "doc.audio"
        txt_file.write_text("This is not audio")
        with pytest.raises(ValueError, match="Invalid file type"):
            validate_audio_file(txt_file)

    def test_rejects_long_recording(self, tmp_path, monkeypatch):
        audio_file = tmp_path / "long.audio"
        audio_file.write_bytes(b"\x00" * 1024)

        # Mock filetype to accept the file
        mock_kind = MagicMock()
        mock_kind.mime = "audio/webm"
        monkeypatch.setattr("filetype.guess", lambda _: mock_kind)

        # Mock mutagen to return long duration
        mock_info = MagicMock()
        mock_info.info.length = 400.0  # >5 minutes
        monkeypatch.setattr("mutagen.File", lambda _: mock_info)

        with pytest.raises(ValueError, match="too long"):
            validate_audio_file(audio_file)

    def test_accepts_valid_short_audio(self, tmp_path, monkeypatch):
        audio_file = tmp_path / "short.audio"
        audio_file.write_bytes(b"\x00" * 1024)

        mock_kind = MagicMock()
        mock_kind.mime = "audio/webm"
        monkeypatch.setattr("filetype.guess", lambda _: mock_kind)

        mock_info = MagicMock()
        mock_info.info.length = 60.0  # 1 minute — fine
        monkeypatch.setattr("mutagen.File", lambda _: mock_info)

        # Should not raise
        validate_audio_file(audio_file)


class TestTranscribeLanguageParam:
    """Tests that transcribe() forwards the language param to faster-whisper."""

    def _make_mock_model(self, transcript_text="Hello."):
        mock_seg = MagicMock()
        mock_seg.text = transcript_text
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_seg], mock_info)
        return mock_model

    def test_explicit_language_forwarded(self, tmp_path):
        from app.services.transcription import transcribe

        audio_file = tmp_path / "test.audio"
        audio_file.write_bytes(b"\x00" * 64)
        mock_model = self._make_mock_model()

        with patch("app.services.transcription._get_model", return_value=mock_model):
            result = transcribe(audio_file, model_name="base", language="en")

        assert result == "Hello."
        mock_model.transcribe.assert_called_once()
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("language") == "en"

    def test_none_language_forwarded_for_auto_detect(self, tmp_path):
        from app.services.transcription import transcribe

        audio_file = tmp_path / "test.audio"
        audio_file.write_bytes(b"\x00" * 64)
        mock_model = self._make_mock_model()

        with patch("app.services.transcription._get_model", return_value=mock_model):
            result = transcribe(audio_file, model_name="base", language=None)

        assert result == "Hello."
        _, kwargs = mock_model.transcribe.call_args
        assert kwargs.get("language") is None
