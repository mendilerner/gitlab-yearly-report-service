"""MCP server exposing the yearly-report functions as tools over stdio.

A second front end over the same ``ReportService`` as the REST API -- no GitLab
logic is duplicated. The one MCP-specific concern is shaping the core's typed
exceptions into short, actionable messages for an LLM caller (see
``mcp_server.errors``).
"""

from mcp.server.fastmcp import FastMCP

from app.gitlab_client import GitLabError
from app.models import ReportResponse
from app.service import InvalidYearError, ReportService, create_client
from mcp_server.errors import to_tool_error

mcp = FastMCP("gitlab-yearly-report")

# One shared service for the process. create_client() raises ConfigError if
# GITLAB_URL / GITLAB_TOKEN are missing (same fail-fast contract as the web
# service); building it at import time is safe (no event loop needed until a call).
_service = ReportService(create_client())


async def _run(report_coro, project_id_or_path: str | None) -> dict:
    """Await a service call, converting known failures into a clean ToolError.

    Catches only the core's declared exceptions (InvalidYearError and the
    GitLabError family); anything else propagates untouched as a real bug.
    """
    try:
        report: ReportResponse = await report_coro
    except (InvalidYearError, GitLabError) as exc:
        raise to_tool_error(exc, project_id_or_path) from exc
    return report.model_dump()


# FastMCP builds each tool's schema from the signature and docstring: the
# docstring becomes the description and the type hints become the input schema.
@mcp.tool()
async def get_issues_by_year(year: int, project_id_or_path: str | None = None) -> dict:
    """Return GitLab issues created during the given year.

    Args:
        year: 4-digit year, e.g. 2025.
        project_id_or_path: GitLab numeric project ID or "group/project" path.
            Omit for an instance-wide report across all projects the token can see.

    Returns a dict {count, truncated, items[...]}. When `truncated` is true the
    year had more results than the page cap and the item list is incomplete.
    """
    return await _run(
        _service.get_issues_by_year(year, project_id_or_path), project_id_or_path
    )


@mcp.tool()
async def get_merge_requests_by_year(
    year: int, project_id_or_path: str | None = None
) -> dict:
    """Return GitLab merge requests created during the given year.

    Args:
        year: 4-digit year, e.g. 2025.
        project_id_or_path: GitLab numeric project ID or "group/project" path.
            Omit for an instance-wide report across all projects the token can see.

    Returns a dict {count, truncated, items[...]}. When `truncated` is true the
    year had more results than the page cap and the item list is incomplete.
    """
    return await _run(
        _service.get_merge_requests_by_year(year, project_id_or_path),
        project_id_or_path,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
