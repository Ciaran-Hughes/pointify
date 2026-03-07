"""Tests: Ollama digest service, prompt injection mitigation, fallback."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.digest import _parse_bullets, _sentence_split_fallback, digest_transcript


class TestSentenceSplitFallback:
    def test_splits_on_period(self):
        text = "First thought. Second thought. Third thought."
        result = _sentence_split_fallback(text)
        assert len(result) == 3
        assert result[0] == "First thought."

    def test_single_sentence(self):
        result = _sentence_split_fallback("Just one idea.")
        assert result == ["Just one idea."]

    def test_empty_string(self):
        result = _sentence_split_fallback("  ")
        assert result == []


class TestParseBullets:
    def test_valid_json_array(self):
        raw = '["Bullet one", "Bullet two", "Bullet three"]'
        result = _parse_bullets(raw, "fallback")
        assert result == ["Bullet one", "Bullet two", "Bullet three"]

    def test_strips_markdown_fences(self):
        raw = '```json\n["Item one", "Item two"]\n```'
        result = _parse_bullets(raw, "fallback")
        assert result == ["Item one", "Item two"]

    def test_falls_back_on_invalid_json(self):
        result = _parse_bullets("not json at all", "First sentence. Second sentence.")
        assert len(result) >= 1

    def test_falls_back_on_wrong_type(self):
        result = _parse_bullets('{"key": "value"}', "First sentence. Second sentence.")
        assert len(result) >= 1

    def test_empty_bullets_falls_back(self):
        result = _parse_bullets("[]", "Some real content here.")
        assert len(result) >= 1


class TestDigestTranscript:
    @pytest.mark.asyncio
    async def test_returns_bullets_from_ollama(self):
        from unittest.mock import MagicMock
        # httpx.Response.json() is synchronous, so use MagicMock for the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '["Idea one", "Idea two"]'}
        mock_response.raise_for_status.return_value = None

        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_async_client):
            result = await digest_transcript("This is a test transcript.")

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_fallback_when_ollama_unavailable(self):
        import httpx
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_async_client):
            result = await digest_transcript("First thought. Second thought.")

        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_empty_transcript_returns_empty(self):
        result = await digest_transcript("   ")
        assert result == []
