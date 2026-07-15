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
    Author,
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


def _year_bounds(year: int) -> tuple[str, str]:
    """Inclusive UTC boundaries for a calendar year.

    GitLab's ``created_after`` / ``created_before`` are both *inclusive* ("on or
    after" / "on or before"), verified against the API. We end the range at the
    last microsecond of the year (GitLab stores ``created_at`` at microsecond
    precision), so adjacent years stay disjoint: using next-year midnight would
    double-count an item created at exactly Jan 1 00:00:00 of the following year,
    since that instant is inclusive in both years.
    """
    return f"{year}-01-01T00:00:00Z", f"{year}-12-31T23:59:59.999999Z"


def _summarize(model: type[ItemSummary], raw: dict[str, Any]) -> ItemSummary:
    author = raw.get("author")
    return model(
        id=raw["id"],
        iid=raw.get("iid"),
        title=raw.get("title", ""),
        state=raw.get("state", ""),
        author=Author(username=author.get("username"), name=author.get("name"))
        if author
        else None,
        created_at=raw.get("created_at", ""),
        web_url=raw.get("web_url", ""),
        project_id=raw.get("project_id"),
    )


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
            raise ValueError(f"year must be a 4-digit year ({MIN_YEAR}-{MAX_YEAR})")
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
        summaries = [_summarize(model, raw) for raw in items]
        return ReportResponse(
            count=len(summaries), truncated=truncated, items=summaries
        )
