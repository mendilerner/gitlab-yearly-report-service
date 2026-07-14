# CLAUDE.md — GitLab Yearly Report Service

## Context
Home assignment for a Mobileye DevOps interview. A read-only reporting service over the GitLab REST API v4: issues and merge requests created in a given year, for one project or the whole instance. The full task breakdown is in `PLAN.md` — work phase by phase, in order. Do not start a phase that wasn't requested.

## Hard requirements from the spec (do not deviate)
- **Read-only**: only GET requests to GitLab. Never POST/PUT/PATCH/DELETE, anywhere.
- **Error contract**: missing/invalid `year` → **400, not 422**. FastAPI's default validation returns 422 — override `RequestValidationError` to return 400. Other mappings: GitLab 401→401, 403→403, project not found→404, missing token → clear startup failure.
- `GET /health` returns exactly `{"status": "ok"}`.
- Config only via env vars, exact names: `GITLAB_URL`, `GITLAB_TOKEN`. Service listens on port **8080**.
- Endpoint paths exactly as in spec: `/issues`, `/merge-requests` (hyphen), query params `year`, `project`.

## Project-specific decisions (already made — don't revisit)
- Package/env management with **uv** (`pyproject.toml` + `uv.lock`), not pip/requirements.txt.
- Async **httpx** client, one shared pagination generator (`per_page=100`, follow `X-Next-Page`).
- Instance-wide queries (`/issues`, `/merge_requests` without project) **must pass `scope=all`** — GitLab defaults to `created_by_me`.
- Year filtering happens on the GitLab side via `created_after` / `created_before` (UTC year boundaries), never by fetching all and filtering in Python.
- `project` query param arrives URL-decoded — **re-encode with `urllib.parse.quote(value, safe="")`** before building the GitLab URL path.
- Pagination safety cap: env var `MAX_PAGES` (default 50). When hit, stop and set `truncated: true` in the response.
- Response shape: `{"count": N, "truncated": bool, "items": [...]}` with slim items (id, iid, title, state, author, created_at, web_url, project_id) — not raw GitLab JSON.
- The MCP server (bonus phase) must call the same functions in `app/service.py`. Do not duplicate GitLab logic.

## Scope guardrails
- This is an interview assignment: prefer simple, readable code over clever abstractions. No features beyond `PLAN.md` (no caching, no DB, no auth layer, no UI, no extra endpoints) unless explicitly asked.
- Never commit secrets. `.env` is gitignored; only `.env.example` with empty values goes in the repo.
- The developer is intermediate-level and will defend this code in an interview: when you make a non-obvious choice, state it briefly in the commit message or a short comment.

## Verification per phase
After each phase, run: `uv run ruff check` and `uv run pytest` (once tests exist). For API phases, also verify manually: missing year → 400, `year=abc` → 400.
