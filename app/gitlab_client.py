"""Async, read-only GitLab REST API v4 client.

The client exposes GET only (read-only guarantee) and centralizes two concerns:
pagination (follow the ``X-Next-Page`` header, capped by ``max_pages``) and
error mapping (HTTP status -> typed exception the API layer turns into 401/403/
404/502).
"""

from collections.abc import AsyncIterator
from typing import Any

import httpx

PER_PAGE = 100
DEFAULT_TIMEOUT = 15.0


class GitLabError(Exception):
    """Base class for GitLab client errors."""


class GitLabAuthError(GitLabError):
    """401 - authentication failed (bad or missing token)."""


class GitLabForbiddenError(GitLabError):
    """403 - authenticated but not permitted."""


class GitLabNotFoundError(GitLabError):
    """404 - resource (e.g. project) not found."""


class GitLabUnavailableError(GitLabError):
    """5xx or network/transport failure - GitLab is unreachable."""


def _detail(response: httpx.Response) -> str:
    """Best-effort human-readable message from a GitLab error body."""
    try:
        body = response.json()
    except ValueError:
        return response.text or response.reason_phrase
    if isinstance(body, dict):
        return str(body.get("message") or body.get("error") or body)
    return str(body)


class GitLabClient:
    """Thin async wrapper over httpx for read-only GitLab access."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        max_pages: int = 10,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._max_pages = max_pages
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/api/v4",
            headers={"PRIVATE-TOKEN": token},
            timeout=timeout,
        )

    async def __aenter__(self) -> "GitLabClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any]) -> httpx.Response:
        """Perform one GET, mapping transport/HTTP errors to typed exceptions."""
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            # httpx timeout exceptions stringify to "" -- say something useful.
            raise GitLabUnavailableError(
                f"GitLab request timed out after {self._timeout}s (GET {path})"
            ) from exc
        except httpx.HTTPError as exc:
            raise GitLabUnavailableError(
                f"GitLab request failed: {type(exc).__name__}: {exc}"
            ) from exc
        self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        status = response.status_code
        detail = _detail(response)
        if status == 401:
            raise GitLabAuthError(detail)
        if status == 403:
            raise GitLabForbiddenError(detail)
        if status == 404:
            raise GitLabNotFoundError(detail)
        if status >= 500:
            raise GitLabUnavailableError(detail)
        # Other 4xx (e.g. 429, 400) - surface as a generic client error.
        raise GitLabError(f"GitLab returned {status}: {detail}")

    async def _pages(
        self, path: str, params: dict[str, Any]
    ) -> AsyncIterator[tuple[list[dict[str, Any]], bool]]:
        """Async generator over pages: yields (items, has_next_page).

        Follows GitLab's ``X-Next-Page`` header until it is empty. ``has_next``
        lets the caller decide whether the safety cap actually truncated results.
        """
        next_page = 1
        while next_page:
            response = await self._get(
                path, {**params, "per_page": PER_PAGE, "page": next_page}
            )
            # X-Next-Page is a page number, or empty on the last page. Only trust
            # a plain ASCII-numeric header; anything unexpected -> stop (no more
            # pages) rather than raising ValueError. isascii() rules out Unicode
            # digits that isdigit() accepts but int() rejects; both are False for "".
            header = response.headers.get("X-Next-Page", "").strip()
            next_page = int(header) if header.isascii() and header.isdigit() else 0
            yield response.json(), bool(next_page)

    async def collect(
        self, path: str, params: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], bool]:
        """Collect all items for a query, honoring the ``max_pages`` cap.

        Returns ``(items, truncated)`` where ``truncated`` is True iff more pages
        existed but we stopped at the cap.
        """
        items: list[dict[str, Any]] = []
        truncated = False
        pages = 0
        async for batch, has_next in self._pages(path, params):
            items.extend(batch)
            pages += 1
            if has_next and pages >= self._max_pages:
                truncated = True
                break
        return items, truncated
