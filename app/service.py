"""Core reporting functions shared by the REST API and the MCP server.

Both entry points call these two functions; GitLab logic lives here only.
Year filtering is done server-side via ``created_after`` / ``created_before``
(never by fetching everything and filtering in Python).
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


async def _report(
    client: GitLabClient,
    resource: str,
    model: type[ItemSummary],
    year: int,
    project_id_or_path: str | int | None,
) -> ReportResponse:
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

    items, truncated = await client.collect(path, params)
    summaries = [_summarize(model, raw) for raw in items]
    return ReportResponse(count=len(summaries), truncated=truncated, items=summaries)


def create_client() -> GitLabClient:
    """Build a GitLabClient from settings. Raises ConfigError if env is missing."""
    settings = get_settings()
    return GitLabClient(
        settings.gitlab_url,
        settings.gitlab_token,
        max_pages=settings.max_pages,
    )


# Process-wide shared client, registered by the app at startup (see use_client).
# When unset -- a direct call or the MCP server -- each call owns a short-lived
# client and closes it. Keeps the public signatures exactly as the spec defines.
_client: GitLabClient | None = None


def use_client(client: GitLabClient | None) -> None:
    """Register the shared client (FastAPI lifespan). Pass None to reset (shutdown/tests)."""
    global _client
    _client = client


async def _run(
    resource: str,
    model: type[ItemSummary],
    year: int,
    project_id_or_path: str | int | None,
) -> ReportResponse:
    if _client is not None:
        return await _report(_client, resource, model, year, project_id_or_path)
    async with create_client() as owned:
        return await _report(owned, resource, model, year, project_id_or_path)


async def get_issues_by_year(
    year: int,
    project_id_or_path: str | int | None = None,
) -> ReportResponse:
    """Issues created during ``year``, for one project or the whole instance."""
    return await _run("issues", IssueSummary, year, project_id_or_path)


async def get_merge_requests_by_year(
    year: int,
    project_id_or_path: str | int | None = None,
) -> ReportResponse:
    """Merge requests created during ``year``, for one project or the instance."""
    return await _run("merge_requests", MergeRequestSummary, year, project_id_or_path)
