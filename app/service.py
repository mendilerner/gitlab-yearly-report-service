"""Core reporting logic shared by the REST API and the MCP server.

``ReportService`` wraps a single ``GitLabClient`` and exposes the two spec
functions as methods. Both entry points construct one service (the API on
``app.state``, the MCP server as a module singleton) and reuse it; GitLab logic
lives here only. Year filtering is done server-side via ``created_after`` /
``created_before`` (never by fetching everything and filtering in Python).
"""

from typing import Any
from urllib.parse import quote

from app.config import get_settings
from app.gitlab_client import GitLabClient
from app.models import (
    IssueSummary,
    ItemSummary,
    MergeRequestSummary,
    ReportResponse,
)


# The spec defines year as a 4-digit value. The core enforces it so non-HTTP
# callers (MCP) reject out-of-range years too; the REST layer additionally
# declares these bounds on its query param for a 400 at the edge and OpenAPI docs.
MIN_YEAR = 1000
MAX_YEAR = 9999


class InvalidYearError(ValueError):
    """The year argument is not a 4-digit year.

    A dedicated type (still a ``ValueError``) so callers can distinguish this
    known input-contract violation from an unrelated ``ValueError`` bug and give
    it a precise message.
    """


def _year_bounds(year: int) -> tuple[str, str]:
    """UTC boundaries for a calendar year. GitLab's created_after/created_before
    are both inclusive, so we end at the last microsecond of the year to keep
    adjacent years disjoint (next-year midnight would double-count)."""
    return f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59.999999Z"


def create_client() -> GitLabClient:
    """Build a GitLabClient from settings. Raises ConfigError if env is missing."""
    settings = get_settings()
    return GitLabClient(
        settings.gitlab_url,
        settings.gitlab_token,
        max_pages=settings.max_pages,
    )


class ReportService:
    """Read-only yearly reporting over a GitLab client. Construct once, reuse.

    The client is an explicit constructor dependency: the API injects the shared
    client via ``app.state``, and tests pass a mocked client -- no global state.
    """

    def __init__(self, client: GitLabClient) -> None:
        self._client = client

    async def get_issues_by_year(
        self,
        year: int,
        project_id_or_path: str | int | None = None,
    ) -> ReportResponse:
        """Issues created during ``year``, for one project or the whole instance."""
        return await self._report("issues", IssueSummary, year, project_id_or_path)

    async def get_merge_requests_by_year(
        self,
        year: int,
        project_id_or_path: str | int | None = None,
    ) -> ReportResponse:
        """Merge requests created during ``year``, for one project or the instance."""
        return await self._report(
            "merge_requests", MergeRequestSummary, year, project_id_or_path
        )

    async def _report(
        self,
        resource: str,
        model: type[ItemSummary],
        year: int,
        project_id_or_path: str | int | None,
    ) -> ReportResponse:
        if not MIN_YEAR <= year <= MAX_YEAR:
            raise InvalidYearError(
                f"year must be a 4-digit year ({MIN_YEAR}-{MAX_YEAR})"
            )
        created_after, created_before = _year_bounds(year)
        params: dict[str, Any] = {
            "created_after": created_after,
            "created_before": created_before,
        }
        if project_id_or_path is not None:
            # The query param arrives URL-decoded; re-encode so "group/project"
            # becomes "group%2Fproject" in the path. Numeric IDs pass through.
            encoded = quote(str(project_id_or_path), safe="")
            path = f"/projects/{encoded}/{resource}"
        else:
            # Instance-wide default is scope=created_by_me; force scope=all.
            path = f"/{resource}"
            params["scope"] = "all"

        items, truncated = await self._client.collect(path, params)
        summaries = [model.from_gitlab(raw) for raw in items]
        return ReportResponse(
            count=len(summaries), truncated=truncated, items=summaries
        )
