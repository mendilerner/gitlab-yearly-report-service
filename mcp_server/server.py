"""MCP server exposing the yearly-report functions as tools over stdio.

A second front end over the same core as the REST API: both build a
``ReportService`` (``app/service.py``) and call it. No GitLab logic is
duplicated here — this module only adapts the service to MCP's tool interface.
"""

from mcp.server.fastmcp import FastMCP

from app.models import ReportResponse
from app.service import ReportService, create_client

mcp = FastMCP("gitlab-yearly-report")

# One shared service for the process. create_client() reads GITLAB_URL /
# GITLAB_TOKEN and raises ConfigError if they are missing (same fail-fast
# contract as the web service). Building it at import time is safe: the
# httpx client only needs the event loop when a request is made.
_service = ReportService(create_client())


# FastMCP builds each tool's schema from the signature and docstring: the
# docstring becomes the description and the type hints become the input schema.
@mcp.tool()
async def get_issues_by_year(year: int, project_id_or_path: str | None = None) -> dict:
    """Return GitLab issues created during the given year.

    Args:
        year: 4-digit year, e.g. 2025.
        project_id_or_path: GitLab numeric project ID or "group/project" path.
            Omit for an instance-wide report across all projects the token can see.
    """
    report: ReportResponse = await _service.get_issues_by_year(year, project_id_or_path)
    return report.model_dump()


@mcp.tool()
async def get_merge_requests_by_year(
    year: int, project_id_or_path: str | None = None
) -> dict:
    """Return GitLab merge requests created during the given year.

    Args:
        year: 4-digit year, e.g. 2025.
        project_id_or_path: GitLab numeric project ID or "group/project" path.
            Omit for an instance-wide report across all projects the token can see.
    """
    report: ReportResponse = await _service.get_merge_requests_by_year(
        year, project_id_or_path
    )
    return report.model_dump()


if __name__ == "__main__":
    mcp.run(transport="stdio")
