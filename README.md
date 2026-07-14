# GitLab Yearly Report Service

A small, **read-only** HTTP service over the GitLab REST API v4. It reports **issues** and
**merge requests created in a given year**, for a single project or the entire GitLab instance
(subject to the token's permissions).

> Mobileye DevOps-IT home assignment. Work is tracked phase-by-phase in [`PLAN.md`](./PLAN.md).

## Status

🚧 Work in progress — Phase 0 (repo setup) complete. See `PLAN.md` for the roadmap.

## Quick start

_Docker instructions land in Phase 4._ For local development:

```bash
uv sync
uv run uvicorn app.api:app --host 0.0.0.0 --port 8080
```

## Configuration

Configuration is via environment variables only (see [`.env.example`](./.env.example)):

| Variable       | Required | Description                                                    |
| -------------- | -------- | -------------------------------------------------------------- |
| `GITLAB_URL`   | yes      | GitLab instance base URL, e.g. `https://gitlab.com`.           |
| `GITLAB_TOKEN` | yes      | Personal access or project token with read permissions.        |
| `MAX_PAGES`    | no       | Pagination safety cap (default 50). When hit, `truncated: true`. |

## API

| Endpoint                                   | Description                                  |
| ------------------------------------------ | -------------------------------------------- |
| `GET /health`                              | Returns `{"status": "ok"}`.                  |
| `GET /issues?year=YYYY&project=<id-or-path>`         | Issues created in the given year.  |
| `GET /merge-requests?year=YYYY&project=<id-or-path>` | Merge requests created in the year. |

`project` is optional; without it, results span the whole instance. Detailed reference,
curl examples, and design notes are added in Phase 6.

## Development

```bash
uv run ruff check
uv run pytest
```
