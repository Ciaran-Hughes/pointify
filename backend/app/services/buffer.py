"""
Buffer Ideas integration service.

SECURITY:
- BUFFER_API_TOKEN is env-var only — never user-configurable, never logged.
- Endpoint is hardcoded to https://api.buffer.com — not user-configurable (SSRF prevention).
- Org ID is either from env or auto-discovered once and cached in memory.
- All errors are handled gracefully; callers get None on best-effort paths.
"""

import logging
import re
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("pointify.buffer")

_BUFFER_ENDPOINT = "https://api.buffer.com"

# Word-boundary pattern: matches "add to buffer" or standalone "buffer"
# but NOT "buffering", "unbuffered", etc.
_TRIGGER_RE = re.compile(
    r"(?:add\s+to\s+buffer|(?<!\w)buffer(?!\w))",
    re.IGNORECASE,
)

# In-memory cache for the auto-discovered org ID (lives for the process lifetime)
_cached_org_id: Optional[str] = None


class BufferAPIError(Exception):
    """Raised when the Buffer API returns an error we should surface to the caller."""


class BufferUnauthorizedError(BufferAPIError):
    """Raised when Buffer returns Unauthorized / bad token."""


def is_buffer_trigger(text: str) -> bool:
    """Return True if the bullet text contains the Buffer trigger phrase."""
    return bool(_TRIGGER_RE.search(text))


def strip_buffer_trigger(text: str) -> str:
    """
    Remove the Buffer trigger phrase from bullet text before sending to Buffer.
    Returns the cleaned text, or an empty string if only the trigger remains.
    """
    cleaned = _TRIGGER_RE.sub("", text).strip().strip(",").strip()
    return cleaned


async def _get_org_id() -> str:
    """
    Return the organization ID to use for createIdea.

    Priority:
      1. BUFFER_ORGANIZATION_ID env var (if set).
      2. Auto-discovered from Buffer's account query (cached for process lifetime).
    """
    global _cached_org_id

    if settings.buffer_organization_id:
        return settings.buffer_organization_id

    if _cached_org_id:
        return _cached_org_id

    _cached_org_id = await fetch_organization_id()
    return _cached_org_id


async def fetch_organization_id() -> str:
    """
    Query Buffer's API to retrieve the first organization ID for this token.
    Raises BufferError if no organizations are found.
    Raises BufferUnauthorizedError on 401.
    """
    query = """
    query GetOrganizations {
      account {
        organizations {
          id
        }
      }
    }
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                _BUFFER_ENDPOINT,
                json={"query": query},
                headers={
                    "Authorization": f"Bearer {settings.buffer_api_token}",
                    "Content-Type": "application/json",
                },
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise BufferAPIError(f"Buffer unreachable: {type(exc).__name__}") from exc

    if response.status_code == 401:
        raise BufferUnauthorizedError("Buffer API token is invalid or expired")

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise BufferAPIError(f"Buffer returned HTTP {response.status_code}") from exc

    data = response.json()
    orgs = data.get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        raise BufferAPIError("No Buffer organizations found for this token")

    return orgs[0]["id"]


async def create_idea(text: str, title: str | None = None) -> Optional[str]:
    """
    Create a Buffer Idea with the given text and optional title.
    Returns the Buffer Idea ID on success, or None if the request fails
    (best-effort: callers should not crash on None).

    Raises BufferUnauthorizedError if the token is invalid — callers may want to
    surface this specifically (e.g. return 502 vs silently skip).
    """
    if not settings.buffer_enabled:
        return None

    try:
        org_id = await _get_org_id()
    except BufferUnauthorizedError:
        raise
    except BufferError as exc:
        logger.warning("Could not resolve Buffer org ID", extra={"error": str(exc)})
        return None

    mutation = """
    mutation CreateIdea($input: CreateIdeaInput!) {
      createIdea(input: $input) {
        ... on Idea {
          id
        }
        ... on IdeaResponse {
          idea {
            id
          }
        }
        ... on InvalidInputError {
          message
          type: __typename
        }
        ... on UnauthorizedError {
          message
          type: __typename
        }
        ... on LimitReachedError {
          message
          type: __typename
        }
        ... on UnexpectedError {
          message
          type: __typename
        }
      }
    }
    """

    content: dict = {"text": text}
    if title:
        content["title"] = title

    variables = {
        "input": {
            "organizationId": org_id,
            "content": content,
        }
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(
                _BUFFER_ENDPOINT,
                json={"query": mutation, "variables": variables},
                headers={
                    "Authorization": f"Bearer {settings.buffer_api_token}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.TimeoutException as exc:
            logger.warning("Buffer request timed out", extra={"error": type(exc).__name__})
            return None
        except httpx.ConnectError as exc:
            logger.warning("Buffer unreachable", extra={"error": type(exc).__name__})
            return None

    if response.status_code == 401:
        raise BufferUnauthorizedError("Buffer API token is invalid or expired")

    if not response.is_success:
        logger.warning("Buffer returned non-2xx", extra={"status": response.status_code})
        return None

    payload = response.json()
    result = payload.get("data", {}).get("createIdea", {})

    # Success paths
    if result.get("id"):
        return result["id"]
    if result.get("idea", {}).get("id"):
        return result["idea"]["id"]

    # Error union types
    typename = result.get("type") or result.get("__typename", "")
    message = result.get("message", "unknown error")
    if typename == "UnauthorizedError":
        raise BufferUnauthorizedError(f"Buffer unauthorized: {message}")

    logger.warning(
        "Buffer createIdea returned error",
        extra={"type": typename, "buffer_message": message},
    )
    return None
