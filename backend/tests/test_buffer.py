"""
Tests for the Buffer integration:
  - Service unit tests (mocked httpx)
  - Endpoint tests (IDOR, idempotency, disabled feature, auth failure)
  - Voice trigger phrase tests (filtering and stripping)
  - Recording upload integration (buffer auto-send, failure isolation)
"""

import io
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import settings
from app.models import BulletPoint, Page
from app.services.buffer import (
    BufferAPIError,
    BufferUnauthorizedError,
    create_idea,
    fetch_organization_id,
    is_buffer_trigger,
    strip_buffer_trigger,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_bullet(db, page_id, text="Test bullet", buffer_idea_id=None):
    bp = BulletPoint(
        page_id=page_id,
        day=date.today(),
        text=text,
        sort_order=0,
        buffer_idea_id=buffer_idea_id,
    )
    db.add(bp)
    db.commit()
    db.refresh(bp)
    return bp


def _mock_httpx_response(json_body: dict, status_code: int = 200):
    """Return a mock httpx.Response-like object."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.is_success = status_code < 400
    mock.json.return_value = json_body
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock
        )
    return mock


# ── Trigger-phrase helpers ────────────────────────────────────────────────────

class TestTriggerPhrase:
    def test_is_buffer_trigger_add_to_buffer(self):
        assert is_buffer_trigger("Buy groceries add to buffer")

    def test_is_buffer_trigger_standalone_buffer(self):
        assert is_buffer_trigger("My cool idea buffer")

    def test_is_buffer_trigger_case_insensitive(self):
        assert is_buffer_trigger("Add To Buffer this idea")
        assert is_buffer_trigger("remember BUFFER this")

    def test_no_trigger_buffering(self):
        assert not is_buffer_trigger("buffering the video")

    def test_no_trigger_unbuffered(self):
        assert not is_buffer_trigger("unbuffered stream rocks")

    def test_no_trigger_normal_text(self):
        assert not is_buffer_trigger("just a regular note here")

    def test_strip_add_to_buffer_suffix(self):
        assert strip_buffer_trigger("Buy groceries add to buffer") == "Buy groceries"

    def test_strip_buffer_only_returns_empty(self):
        result = strip_buffer_trigger("buffer")
        assert result == ""

    def test_strip_buffer_mid_sentence(self):
        result = strip_buffer_trigger("Go buffer running at 6am")
        assert "buffer" not in result.lower()
        assert result.strip() != ""

    def test_strip_does_not_touch_buffering(self):
        # "buffering" should not be matched/stripped (covered by regex word boundary)
        original = "buffering video"
        assert not is_buffer_trigger(original)


# ── Buffer service unit tests (mocked httpx) ─────────────────────────────────

class TestBufferService:
    """Service-level tests that mock httpx directly."""

    @pytest.mark.asyncio
    async def test_create_idea_success(self):
        idea_id = "507f1f77bcf86cd799439011"
        response_body = {
            "data": {
                "createIdea": {
                    "id": idea_id,
                }
            }
        }
        mock_response = _mock_httpx_response(response_body)

        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch.object(settings, "buffer_organization_id", "org-123"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await create_idea("My cool idea")

        assert result == idea_id
        # Verify the mutation was called with correct variables
        call_kwargs = mock_client.post.call_args
        body = call_kwargs[1]["json"] if call_kwargs[1] else call_kwargs[0][1]
        assert "createIdea" in body["query"]
        assert body["variables"]["input"]["content"]["text"] == "My cool idea"
        assert body["variables"]["input"]["organizationId"] == "org-123"

    @pytest.mark.asyncio
    async def test_create_idea_returns_none_when_disabled(self):
        with patch.object(settings, "buffer_api_token", ""):
            result = await create_idea("some text")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_idea_unauthorized_raises(self):
        mock_response = _mock_httpx_response({}, status_code=401)

        with patch.object(settings, "buffer_api_token", "bad-token"), \
             patch.object(settings, "buffer_organization_id", "org-123"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(BufferUnauthorizedError):
                await create_idea("My idea")

    @pytest.mark.asyncio
    async def test_create_idea_timeout_returns_none(self):
        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch.object(settings, "buffer_organization_id", "org-123"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client_cls.return_value = mock_client

            result = await create_idea("My idea")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_idea_connect_error_returns_none(self):
        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch.object(settings, "buffer_organization_id", "org-123"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client_cls.return_value = mock_client

            result = await create_idea("My idea")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_idea_unexpected_error_union_returns_none(self):
        response_body = {
            "data": {
                "createIdea": {
                    "type": "UnexpectedError",
                    "message": "something went wrong",
                }
            }
        }
        mock_response = _mock_httpx_response(response_body)

        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch.object(settings, "buffer_organization_id", "org-123"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await create_idea("My idea")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_idea_unauthorized_union_raises(self):
        response_body = {
            "data": {
                "createIdea": {
                    "type": "UnauthorizedError",
                    "message": "not authorized",
                }
            }
        }
        mock_response = _mock_httpx_response(response_body)

        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch.object(settings, "buffer_organization_id", "org-123"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(BufferUnauthorizedError):
                await create_idea("My idea")

    @pytest.mark.asyncio
    async def test_fetch_organization_id_success(self):
        org_id = "org-abc-123"
        response_body = {
            "data": {
                "account": {
                    "organizations": [{"id": org_id}]
                }
            }
        }
        mock_response = _mock_httpx_response(response_body)

        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch_organization_id()

        assert result == org_id

    @pytest.mark.asyncio
    async def test_fetch_organization_id_no_orgs_raises(self):
        response_body = {
            "data": {
                "account": {
                    "organizations": []
                }
            }
        }
        mock_response = _mock_httpx_response(response_body)

        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(BufferAPIError, match="No Buffer organizations"):
                await fetch_organization_id()

    @pytest.mark.asyncio
    async def test_fetch_organization_id_unauthorized_raises(self):
        mock_response = _mock_httpx_response({}, status_code=401)

        with patch.object(settings, "buffer_api_token", "bad-token"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(BufferUnauthorizedError):
                await fetch_organization_id()

    @pytest.mark.asyncio
    async def test_org_id_env_var_skips_http(self):
        """When BUFFER_ORGANIZATION_ID is set, no HTTP call should be made."""
        import app.services.buffer as buf_module

        # Reset cache to test env var path
        original_cache = buf_module._cached_org_id
        buf_module._cached_org_id = None

        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch.object(settings, "buffer_organization_id", "env-org-id"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            org_id = await buf_module._get_org_id()

        assert org_id == "env-org-id"
        mock_client_cls.assert_not_called()
        buf_module._cached_org_id = original_cache  # restore

    @pytest.mark.asyncio
    async def test_org_id_is_cached(self):
        """After first fetch, subsequent calls must not make another HTTP request."""
        import app.services.buffer as buf_module

        buf_module._cached_org_id = None

        org_id = "cached-org-123"
        response_body = {"data": {"account": {"organizations": [{"id": org_id}]}}}
        mock_response = _mock_httpx_response(response_body)

        with patch.object(settings, "buffer_api_token", "test-token"), \
             patch.object(settings, "buffer_organization_id", ""), \
             patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            first = await buf_module._get_org_id()
            second = await buf_module._get_org_id()

        assert first == org_id
        assert second == org_id
        # Only one HTTP call (first fetch); second uses cache
        assert mock_client.post.call_count == 1

        buf_module._cached_org_id = None  # clean up


# ── Endpoint tests ────────────────────────────────────────────────────────────

class TestSendToBufferEndpoint:

    def test_send_to_buffer_success(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id, "A great idea")
        idea_id = "buffer-idea-abc"

        with patch("app.routers.bullets.create_idea", new=AsyncMock(return_value=idea_id)), \
             patch.object(settings, "buffer_api_token", "test-token"):
            r = client.post(f"/api/v1/bullets/{bp.id}/buffer", headers=user_headers)

        assert r.status_code == 200
        data = r.json()
        assert data["buffer_idea_id"] == idea_id
        assert data["bullet_id"] == str(bp.id)

        db.refresh(bp)
        assert bp.buffer_idea_id == idea_id

    def test_send_to_buffer_already_sent_returns_409(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id, "Already in Buffer", buffer_idea_id="existing-id")

        with patch.object(settings, "buffer_api_token", "test-token"):
            r = client.post(f"/api/v1/bullets/{bp.id}/buffer", headers=user_headers)

        assert r.status_code == 409
        assert r.json()["detail"]["error_code"] == "BUFFER_ALREADY_SENT"

    def test_send_to_buffer_feature_disabled_returns_501(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id, "Some idea")

        with patch.object(settings, "buffer_api_token", ""):
            r = client.post(f"/api/v1/bullets/{bp.id}/buffer", headers=user_headers)

        assert r.status_code == 501
        assert r.json()["detail"]["error_code"] == "BUFFER_NOT_CONFIGURED"

    def test_send_to_buffer_nonexistent_bullet_returns_404(self, client, regular_user, user_headers, db):
        fake_id = uuid.uuid4()
        with patch.object(settings, "buffer_api_token", "test-token"):
            r = client.post(f"/api/v1/bullets/{fake_id}/buffer", headers=user_headers)

        assert r.status_code == 404

    def test_send_to_buffer_idor_blocked(self, client, second_user, user_headers, db):
        """User A cannot send user B's bullet to Buffer."""
        other_page = Page(user_id=second_user.id, name="Other page")
        db.add(other_page)
        db.commit()
        bp = _make_bullet(db, other_page.id, "Private idea")

        with patch.object(settings, "buffer_api_token", "test-token"):
            r = client.post(f"/api/v1/bullets/{bp.id}/buffer", headers=user_headers)

        assert r.status_code == 404

    def test_send_to_buffer_unauthorized_token_returns_502(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id, "My idea")

        with patch("app.routers.bullets.create_idea", new=AsyncMock(side_effect=BufferUnauthorizedError("bad token"))), \
             patch.object(settings, "buffer_api_token", "test-token"):
            r = client.post(f"/api/v1/bullets/{bp.id}/buffer", headers=user_headers)

        assert r.status_code == 502
        assert r.json()["detail"]["error_code"] == "BUFFER_UNAUTHORIZED"

    def test_send_to_buffer_api_failure_returns_502(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id, "My idea")

        with patch("app.routers.bullets.create_idea", new=AsyncMock(side_effect=Exception("network error"))), \
             patch.object(settings, "buffer_api_token", "test-token"):
            r = client.post(f"/api/v1/bullets/{bp.id}/buffer", headers=user_headers)

        assert r.status_code == 502
        assert r.json()["detail"]["error_code"] == "BUFFER_ERROR"

    def test_send_to_buffer_no_idea_id_returns_502(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id, "My idea")

        with patch("app.routers.bullets.create_idea", new=AsyncMock(return_value=None)), \
             patch.object(settings, "buffer_api_token", "test-token"):
            r = client.post(f"/api/v1/bullets/{bp.id}/buffer", headers=user_headers)

        assert r.status_code == 502
        assert r.json()["detail"]["error_code"] == "BUFFER_NO_IDEA_ID"

    def test_send_to_buffer_requires_auth(self, client, user_page, db):
        bp = _make_bullet(db, user_page.id)
        with patch.object(settings, "buffer_api_token", "test-token"):
            r = client.post(f"/api/v1/bullets/{bp.id}/buffer")
        assert r.status_code == 401


# ── Health endpoint ───────────────────────────────────────────────────────────

class TestHealthBufferFlag:
    def test_health_buffer_false_when_no_token(self, client):
        with patch.object(settings, "buffer_api_token", ""):
            r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["buffer"] is False

    def test_health_buffer_true_when_token_set(self, client):
        with patch.object(settings, "buffer_api_token", "test-token"):
            r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["buffer"] is True


# ── Voice trigger integration (recording upload) ──────────────────────────────

class TestVoiceTriggerIntegration:
    """Test the recording upload flow for Buffer auto-send behavior."""

    def _minimal_audio(self):
        """Return a minimal valid WAV-like bytes for upload mocking."""
        return io.BytesIO(b"RIFF\x00\x00\x00\x00WAVEfmt ")

    def test_upload_with_buffer_keyword_sends_to_buffer(self, client, regular_user, user_headers, user_page):
        """When a digest bullet contains 'add to buffer', idea should be created."""
        idea_id = "voice-idea-001"

        with patch("app.routers.recordings.validate_audio_file", return_value=None), \
             patch("app.routers.recordings.transcribe", return_value="note: write blog post add to buffer"), \
             patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=["Write blog post add to buffer"])), \
             patch("app.routers.recordings.create_idea", new=AsyncMock(return_value=idea_id)) as mock_create, \
             patch.object(settings, "buffer_api_token", "tok"):

            form_data = {"file": ("rec.webm", self._minimal_audio(), "audio/webm")}
            r = client.post(
                f"/api/v1/pages/{user_page.id}/recordings?whisper_model=base&whisper_language=en",
                files=form_data,
                headers=user_headers,
            )

        assert r.status_code == 201
        mock_create.assert_called_once()
        # Text passed to create_idea should not contain the trigger phrase
        called_text = mock_create.call_args[0][0]
        assert "add to buffer" not in called_text.lower()
        assert "buffer" not in called_text.lower()

    def test_upload_without_buffer_keyword_skips_buffer(self, client, regular_user, user_headers, user_page):
        """Normal bullets without trigger phrase should not call create_idea."""
        with patch("app.routers.recordings.validate_audio_file", return_value=None), \
             patch("app.routers.recordings.transcribe", return_value="remember to buy milk"), \
             patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=["Buy milk"])), \
             patch("app.routers.recordings.create_idea", new=AsyncMock()) as mock_create, \
             patch.object(settings, "buffer_api_token", "tok"):

            form_data = {"file": ("rec.webm", self._minimal_audio(), "audio/webm")}
            r = client.post(
                f"/api/v1/pages/{user_page.id}/recordings?whisper_model=base&whisper_language=en",
                files=form_data,
                headers=user_headers,
            )

        assert r.status_code == 201
        mock_create.assert_not_called()

    def test_upload_buffer_failure_does_not_fail_upload(self, client, regular_user, user_headers, user_page):
        """Even if Buffer raises, the recording upload should still succeed."""
        with patch("app.routers.recordings.validate_audio_file", return_value=None), \
             patch("app.routers.recordings.transcribe", return_value="cool idea add to buffer"), \
             patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=["Cool idea add to buffer"])), \
             patch("app.routers.recordings.create_idea", new=AsyncMock(side_effect=Exception("Buffer down"))), \
             patch.object(settings, "buffer_api_token", "tok"):

            form_data = {"file": ("rec.webm", self._minimal_audio(), "audio/webm")}
            r = client.post(
                f"/api/v1/pages/{user_page.id}/recordings?whisper_model=base&whisper_language=en",
                files=form_data,
                headers=user_headers,
            )

        assert r.status_code == 201

    def test_upload_buffer_disabled_skips_buffer(self, client, regular_user, user_headers, user_page):
        """When buffer is disabled, create_idea should never be called."""
        with patch("app.routers.recordings.validate_audio_file", return_value=None), \
             patch("app.routers.recordings.transcribe", return_value="great idea add to buffer"), \
             patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=["Great idea add to buffer"])), \
             patch("app.routers.recordings.create_idea", new=AsyncMock()) as mock_create, \
             patch.object(settings, "buffer_api_token", ""):

            form_data = {"file": ("rec.webm", self._minimal_audio(), "audio/webm")}
            r = client.post(
                f"/api/v1/pages/{user_page.id}/recordings?whisper_model=base&whisper_language=en",
                files=form_data,
                headers=user_headers,
            )

        assert r.status_code == 201
        mock_create.assert_not_called()

    def test_upload_buffer_unauthorized_stops_early_but_upload_succeeds(self, client, regular_user, user_headers, user_page):
        """If Buffer token is unauthorized, remaining bullets are skipped but upload succeeds."""
        call_count = {"n": 0}

        async def failing_create_idea(text):
            call_count["n"] += 1
            raise BufferUnauthorizedError("bad token")

        with patch("app.routers.recordings.validate_audio_file", return_value=None), \
             patch("app.routers.recordings.transcribe", return_value="idea one buffer, idea two buffer"), \
             patch("app.routers.recordings.digest_transcript", new=AsyncMock(return_value=[
                 "Idea one buffer", "Idea two buffer"
             ])), \
             patch("app.routers.recordings.create_idea", new=failing_create_idea), \
             patch.object(settings, "buffer_api_token", "tok"):

            form_data = {"file": ("rec.webm", self._minimal_audio(), "audio/webm")}
            r = client.post(
                f"/api/v1/pages/{user_page.id}/recordings?whisper_model=base&whisper_language=en",
                files=form_data,
                headers=user_headers,
            )

        assert r.status_code == 201
        # Should stop after first failure
        assert call_count["n"] == 1


# ── BulletResponse schema includes buffer_idea_id ────────────────────────────

class TestBulletResponseSchema:
    def test_bullet_response_includes_buffer_idea_id(self, client, regular_user, user_headers, user_page, db):
        """buffer_idea_id should be present in GET days response."""
        bp = _make_bullet(db, user_page.id, "Test with buffer id", buffer_idea_id="idea-xyz")

        r = client.get(f"/api/v1/pages/{user_page.id}/days", headers=user_headers)
        assert r.status_code == 200

        all_bullets = [
            b
            for day in r.json()
            for b in day.get("orphan_bullets", [])
        ]
        matching = [b for b in all_bullets if b["id"] == str(bp.id)]
        assert len(matching) == 1
        assert matching[0]["buffer_idea_id"] == "idea-xyz"

    def test_bullet_response_buffer_idea_id_null_when_not_sent(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id, "Unsent bullet")

        r = client.get(f"/api/v1/pages/{user_page.id}/days", headers=user_headers)
        assert r.status_code == 200

        all_bullets = [b for day in r.json() for b in day.get("orphan_bullets", [])]
        matching = [b for b in all_bullets if b["id"] == str(bp.id)]
        assert len(matching) == 1
        assert matching[0]["buffer_idea_id"] is None
