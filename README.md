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

## Known limitations

**Instance-wide queries on very large instances.** When `project` is omitted, the service
queries GitLab's global endpoints with `scope=all` (all issues/MRs the token can see), as the
spec requires. On a normally sized instance — including the assignment's local GitLab playground
— this returns quickly. On **GitLab.com specifically**, the unfiltered `scope=all` query exceeds
GitLab's database statement timeout and returns `500` after ~15s (a long-standing GitLab issue,
[gitlab-org/gitlab#22699](https://gitlab.com/gitlab-org/gitlab/-/issues/22699)); the service
surfaces this as `502`. This is a GitLab.com scale limitation, not a defect in the service —
project-scoped queries work everywhere, and instance-wide is validated against the local
playground.

_Bounded alternative:_ where instance-wide `scope=all` is impractical, GitLab's group endpoints
(`GET /groups/:id/issues`, `GET /groups/:id/merge_requests`) aggregate across all projects in a
group and its subgroups without the timeout. It is a narrower scope than "entire instance," so it
is noted here as an option rather than the default behavior.

## Development

```bash
uv run ruff check
uv run pytest
```
