"""FastAPI application exposing the read-only GitLab yearly report endpoints.

Endpoints (paths exactly as the spec requires):
    GET /health          -> {"status": "ok"}
    GET /issues          ?year=&project=
    GET /merge-requests  ?year=&project=

Error contract: missing/invalid year -> 400 (not FastAPI's default 422);
GitLab client exceptions -> 401/403/404/502. Missing token -> fail fast at
startup via the lifespan below.
"""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.gitlab_client import (
    GitLabAuthError,
    GitLabError,
    GitLabForbiddenError,
    GitLabNotFoundError,
    GitLabUnavailableError,
)
from app.models import ReportResponse
from app.service import ReportService, create_client

# GitLab client exception -> HTTP status. Base GitLabError falls through to 502.
_GITLAB_STATUS: dict[type[GitLabError], int] = {
    GitLabAuthError: 401,
    GitLabForbiddenError: 403,
    GitLabNotFoundError: 404,
    GitLabUnavailableError: 502,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_client() calls get_settings(), which raises ConfigError if
    # GITLAB_URL / GITLAB_TOKEN are missing -> uvicorn fails to start with a
    # clear message (assignment requirement). One shared client/service for the
    # process, held on app.state (no module-level global).
    client = create_client()
    app.state.service = ReportService(client)
    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(title="GitLab Yearly Report Service", lifespan=lifespan)


def get_service(request: Request) -> ReportService:
    """The single place that reads the shared service off app.state.

    Injected via Depends so routes stay clean and typed, and tests can override
    it with app.dependency_overrides[get_service].
    """
    return request.app.state.service


ServiceDep = Annotated[ReportService, Depends(get_service)]


def _clean_project(project: str | None) -> str | None:
    """None -> instance-wide. Present-but-blank/whitespace -> 400."""
    if project is None:
        return None
    if not project.strip():
        raise HTTPException(status_code=400, detail="project must not be empty")
    return project


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/issues", response_model=ReportResponse)
async def issues(
    service: ServiceDep,
    year: int = Query(..., ge=1000, le=9999, description="4-digit year, e.g. 2025"),
    project: str | None = Query(None, description="Project ID or path; omit for instance-wide"),
) -> ReportResponse:
    return await service.get_issues_by_year(year, _clean_project(project))


@app.get("/merge-requests", response_model=ReportResponse)
async def merge_requests(
    service: ServiceDep,
    year: int = Query(..., ge=1000, le=9999, description="4-digit year, e.g. 2025"),
    project: str | None = Query(None, description="Project ID or path; omit for instance-wide"),
) -> ReportResponse:
    return await service.get_merge_requests_by_year(year, _clean_project(project))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Spec mandates 400 (not 422) for missing/invalid year.
    errors = exc.errors()
    if errors:
        loc = errors[0].get("loc", [])
        field = loc[-1] if loc else "request"
        detail = f"Invalid or missing parameter '{field}': {errors[0].get('msg', '')}".strip()
    else:
        detail = "Invalid request"
    return JSONResponse(status_code=400, content={"detail": detail})


@app.exception_handler(GitLabError)
async def gitlab_exception_handler(_request: Request, exc: GitLabError) -> JSONResponse:
    # Starlette matches this handler for every GitLabError subclass via the MRO.
    status = next(
        (code for typ, code in _GITLAB_STATUS.items() if isinstance(exc, typ)),
        502,  # base GitLabError / unexpected upstream failure
    )
    return JSONResponse(status_code=status, content={"detail": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8080)
