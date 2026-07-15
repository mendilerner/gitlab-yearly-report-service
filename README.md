# GitLab Yearly Report Service

A small, **read-only** HTTP service over the GitLab REST API v4. It reports the **issues** and
**merge requests created in a given year**, for a single project or for the whole GitLab instance.

> Mobileye DevOps-IT home assignment.

## Quick start (Docker)

```bash
docker build -t gitlab-yearly-report-service .

docker run --rm -p 8080:8080 \
  -e GITLAB_URL=https://gitlab.com \
  -e GITLAB_TOKEN=<your-read-token> \
  gitlab-yearly-report-service
```

The service listens on **port 8080**. A missing `GITLAB_TOKEN` fails fast at startup with a clear
message rather than serving broken requests.

Local development (no Docker) uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run uvicorn app.api:app --host 0.0.0.0 --port 8080
```

## Configuration

Configuration is via environment variables only (see [`.env.example`](./.env.example)):

| Variable       | Required | Description                                                       |
| -------------- | -------- | ----------------------------------------------------------------- |
| `GITLAB_URL`   | yes      | GitLab base URL, e.g. `https://gitlab.com`.                       |
| `GITLAB_TOKEN` | yes      | Personal-access or project token with **read** permissions.       |
| `MAX_PAGES`    | no       | Pagination safety cap (default 50 → 5,000 items). When hit, `truncated: true`. |

## API

| Endpoint                                              | Description                          |
| ----------------------------------------------------- | ------------------------------------ |
| `GET /health`                                         | Liveness. Returns `{"status": "ok"}`. |
| `GET /issues?year=YYYY&project=<id-or-path>`          | Issues created in `year`.            |
| `GET /merge-requests?year=YYYY&project=<id-or-path>`  | Merge requests created in `year`.    |

- `year` is **required**, a 4-digit integer. Missing or invalid → **400**.
- `project` is **optional**: a numeric ID (`42`) or a project path with the slash URL-encoded as
  `%2F` (`mygroup%2Fmy-project`). Omit it for an instance-wide report. (A raw slash also works — the
  service re-encodes it before calling GitLab — but `%2F` is the portable form.)

### Examples

```bash
# Issues in one project, by path (slash encoded as %2F)
curl "http://localhost:8080/issues?year=2025&project=mygroup%2Fmy-project"

# Merge requests in one project, by numeric ID
curl "http://localhost:8080/merge-requests?year=2025&project=42"

# Instance-wide (all projects the token can see) — see Known limitations
curl "http://localhost:8080/issues?year=2025"

# Missing year → 400
curl "http://localhost:8080/issues"
```

### Response shape

Raw GitLab objects are large and noisy, so the service returns a normalized slice:

```json
{
  "count": 2,
  "truncated": false,
  "items": [
    {
      "id": 101,
      "iid": 7,
      "title": "Fix flaky pipeline",
      "state": "closed",
      "author": { "username": "mendi", "name": "Mendi Lerner" },
      "created_at": "2025-03-14T09:12:00.000Z",
      "web_url": "https://gitlab.com/mygroup/my-project/-/issues/7",
      "project_id": 42
    }
  ]
}
```

`truncated` is `true` only when the `MAX_PAGES` safety cap was reached before all pages were read.

### Errors

Errors return `{"detail": "..."}` with the matching status:

| Status | When                                                        |
| ------ | ----------------------------------------------------------- |
| `400`  | Missing/invalid `year`, or blank `project`.                 |
| `401`  | GitLab rejected the token.                                  |
| `403`  | Token lacks permission for the resource.                    |
| `404`  | Project not found.                                          |
| `502`  | GitLab unavailable, timed out, or returned an error.        |

## MCP server (bonus)

The same two functions are also exposed as **MCP tools** (`get_issues_by_year`,
`get_merge_requests_by_year`) over stdio, reusing the exact same `ReportService` as the REST API —
no GitLab logic is duplicated. The MCP SDK is an optional extra, so it is not part of the
web-service Docker image.

**Run** (reads `GITLAB_URL` / `GITLAB_TOKEN` from the environment or `.env`, same as the service):

```bash
uv sync --extra mcp
uv run --extra mcp python -m mcp_server.server
```

**Test** with the MCP Inspector (requires Node) — a UI to list and invoke the tools. Pass the
GitLab env with `-e`:

```bash
npx @modelcontextprotocol/inspector \
  -e GITLAB_URL=https://gitlab.com -e GITLAB_TOKEN=glpat-... \
  uv run --extra mcp python -m mcp_server.server
```

In the browser UI it opens: confirm **Connected**, open the **Tools** tab, click **List Tools**
(it does not auto-populate), then select `get_issues_by_year`, enter a `year` (e.g. `2025`), and
click **Run** to see the result.

## Design decisions

- **Shared core, exposed once.** All GitLab logic lives in `app/gitlab_client.py` (transport:
  pagination, auth header, error mapping) and `app/service.py` (`ReportService`: year bounds,
  scope, response shaping). Both the REST API and the MCP server are thin layers over the same
  `ReportService` — GitLab logic is written once and exposed twice.
- **Server-side year filtering.** Filtering is pushed to GitLab via `created_after` /
  `created_before` (UTC year boundaries), never by fetching everything and filtering in Python.
- **Read-only by construction.** The client only ever issues `GET` requests.
- **Bounded pagination.** Pages are followed via the `X-Next-Page` header at `per_page=100`, up to
  `MAX_PAGES`; hitting the cap sets `truncated: true` instead of running unbounded.
- **Strict error contract.** Missing/invalid `year` returns **400** (FastAPI's default is 422, so
  it's overridden). GitLab errors map to typed exceptions → `401/403/404/502`.

## Known limitations

**Instance-wide queries on GitLab.com.** With `project` omitted, the service uses GitLab's global
endpoints with `scope=all` (all issues/MRs the token can see), as the spec requires. On a normal
instance this is fast. On **GitLab.com specifically**, the unfiltered `scope=all` query exceeds
GitLab's database statement timeout and returns `500` after ~15s (a long-standing GitLab issue,
[gitlab-org/gitlab#22699](https://gitlab.com/gitlab-org/gitlab/-/issues/22699)); the service
surfaces this as `502`. This is a GitLab.com scale limitation, not a defect here — project-scoped
queries work everywhere. Where instance-wide scope is impractical, GitLab's group endpoints
(`GET /groups/:id/issues`) aggregate across a group's projects without the timeout, at a narrower
scope than "entire instance."

Instance-wide queries work correctly against a local **GitLab EE 18.10** playground.

## Development

```bash
uv run ruff check
```
