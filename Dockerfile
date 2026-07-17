# ---- build stage: resolve and install dependencies into a venv with uv ----
FROM python:3.12-slim-bookworm AS build

# uv (build-time only), pinned from its official image.
COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install deps only (no dev, no project) in a layer cached on the lock files.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# ---- runtime stage ----
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="gitlab-yearly-report-service" \
      org.opencontainers.image.description="Read-only GitLab yearly issues/merge-requests reporting service" \
      org.opencontainers.image.source="https://github.com/mendilerner/gitlab-yearly-report-service"

# Unprivileged user.
RUN useradd --create-home app
WORKDIR /app

# Same base image in both stages, so the venv's interpreter symlinks stay valid.
COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app app/ ./app/

USER app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# Stdlib health check (no curl in slim).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).status == 200 else 1)"

# `python -m` puts /app on sys.path so app.api imports without installing it.
CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8080"]
