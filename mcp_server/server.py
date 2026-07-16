"""MCP server exposing the yearly-report functions as tools over stdio.

A second front end over the same core as the REST API: both build a
``ReportService`` (``app/service.py``) and call it. No GitLab logic is
duplicated here — this module only adapts the service to MCP's tool interface.

The one MCP-specific concern handled here is *error shaping for an LLM caller*.
The core raises the same typed exceptions the REST layer maps to HTTP codes; we
translate them into short, actionable messages so the model can tell apart the
three things it might need to do — fix the input, retry later, or report the
problem and stop — instead of receiving a raw GitLab body or stack trace.
"""

from mcp.server.fastmcp import FastMCP

from app.gitlab_client import GitLabError
from app.models import ReportResponse
from app.service import InvalidYearError, ReportService, create_client
from mcp_server.errors import to_tool_error

mcp = FastMCP("gitlab-yearly-report")

# One shared service for the process. create_client() reads GITLAB_URL /
# GITLAB_TOKEN and raises ConfigError if they are missing (same fail-fast
# contract as the web service). Building it at import time is safe: the
# httpx client only needs the event loop when a request is made.
_service = ReportService(create_client())


async def _run(report_coro, project_id_or_path: str | None) -> dict:
    """Await a service call, converting known failures into a clean ToolError.

    We catch only the core's declared exceptions (``InvalidYearError`` and the
    ``GitLabError`` family); anything else propagates untouched so a real bug is
    not disguised as one of these expected conditions. The message mapping lives
    in ``mcp_server.errors``.
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
