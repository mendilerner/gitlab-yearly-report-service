"""Translate core/client exceptions into LLM-facing tool errors.

Kept out of ``server.py`` so the one piece of MCP-specific behavior with real
logic — turning a typed failure into an actionable message — reads and tests on
its own. Each message tells the model *which kind* of problem it hit, so it can
decide whether to fix its input, retry, or stop.
"""

from collections.abc import Callable

from mcp.server.fastmcp.exceptions import ToolError

from app.gitlab_client import (
    GitLabAuthError,
    GitLabForbiddenError,
    GitLabNotFoundError,
    GitLabUnavailableError,
)
from app.service import InvalidYearError

# Auth and permission failures are one story to the caller: the configured token
# is the problem, so retrying with different arguments will not help.
_TOKEN_REJECTED = (
    "GitLab rejected the configured token (authentication or permission "
    "failure). This is a server configuration issue: report it to the user and "
    "stop rather than retrying."
)


def _invalid_year(exc: Exception, _project: str | None) -> str:
    return f"Invalid argument: {exc}. Pass a 4-digit year such as 2025."


def _not_found(_exc: Exception, project: str | None) -> str:
    hint = (
        "Check project_id_or_path (a numeric ID or a 'group/project' path), or "
        "omit it for an instance-wide report."
    )
    if project is not None:
        return f"GitLab project '{project}' was not found. {hint}"
    return f"The requested GitLab resource was not found. {hint}"


def _token_rejected(_exc: Exception, _project: str | None) -> str:
    return _TOKEN_REJECTED


def _unavailable(exc: Exception, _project: str | None) -> str:
    return (
        f"GitLab is unavailable or timed out ({exc}). This may be transient; "
        "retrying later may help."
    )


# Checked top to bottom; the first matching type wins, so list subclasses before
# any base they share. Anything not listed falls through to a generic message.
_RULES: tuple[tuple[type[Exception], Callable[[Exception, str | None], str]], ...] = (
    (InvalidYearError, _invalid_year),
    (GitLabNotFoundError, _not_found),
    (GitLabAuthError, _token_rejected),
    (GitLabForbiddenError, _token_rejected),
    (GitLabUnavailableError, _unavailable),
)


def to_tool_error(exc: Exception, project_id_or_path: str | None) -> ToolError:
    """Build the ToolError to raise for a known core/client exception."""
    for exc_type, build in _RULES:
        if isinstance(exc, exc_type):
            return ToolError(build(exc, project_id_or_path))
    return ToolError(f"GitLab request failed: {exc}")
