"""Tests: Ollama digest service, prompt injection mitigation, fallback."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.digest import _parse_bullets, digest_transcript, generate_idea_title


class TestParseBullets:
    def test_valid_json_array(self):
        raw = '["Bullet one", "Bullet two", "Bullet three"]'
        result = _parse_bullets(raw)
        assert result == ["Bullet one", "Bullet two", "Bullet three"]

    def test_strips_markdown_fences(self):
        raw = '```json\n["Item one", "Item two"]\n```'
        result = _parse_bullets(raw)
        assert result == ["Item one", "Item two"]

    def test_returns_empty_on_invalid_json(self):
        result = _parse_bullets("not json at all")
        assert result == []

    def test_returns_empty_on_wrong_type(self):
        result = _parse_bullets('{"key": "value"}')
        assert result == []

    def test_returns_empty_on_empty_array(self):
        result = _parse_bullets("[]")
        assert result == []


class TestDigestTranscript:
    @pytest.mark.asyncio
    async def test_returns_bullets_from_ollama(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": '["Idea one", "Idea two"]'}}
        mock_response.raise_for_status.return_value = None

        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_async_client):
            result = await digest_transcript("This is a test transcript.")

        assert result == ["Idea one", "Idea two"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_ollama_unavailable(self):
        mock_async_client = AsyncMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)
        mock_async_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_async_client):
            result = await digest_transcript("First thought. Second thought.")

        assert result == []

    @pytest.mark.asyncio
    async def test_empty_transcript_returns_empty(self):
        result = await digest_transcript("   ")
        assert result == []


class TestGenerateIdeaTitle:
    def _make_ollama_response(self, content: str, status_code: int = 200):
        mock = MagicMock()
        mock.status_code = status_code
        mock.json.return_value = {"message": {"content": content}}
        mock.raise_for_status = MagicMock()
        if status_code >= 400:
            mock.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock
            )
        return mock

    @pytest.mark.asyncio
    async def test_returns_string_from_ollama(self):
        mock_response = self._make_ollama_response("Write That Blog Post")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await generate_idea_title("write a blog post about productivity")

        assert result == "Write That Blog Post"

    @pytest.mark.asyncio
    async def test_returns_none_on_connect_error(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await generate_idea_title("some idea")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await generate_idea_title("some idea")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_response(self):
        mock_response = self._make_ollama_response("")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await generate_idea_title("some idea")

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_input_returns_none(self):
        result = await generate_idea_title("   ")
        assert result is None

    @pytest.mark.asyncio
    async def test_strips_surrounding_quotes_from_title(self):
        mock_response = self._make_ollama_response('"Launch New Product Line"')
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await generate_idea_title("launch a new product line next quarter")

        assert result == "Launch New Product Line"
