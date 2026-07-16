"""Application configuration, loaded from environment variables.

Only the env vars mandated by the spec are read: GITLAB_URL, GITLAB_TOKEN,
plus the project-defined MAX_PAGES pagination cap. Missing required values fail
fast with a clear message (assignment requirement: missing token -> clear
startup failure).
"""

from functools import lru_cache

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    # env vars are matched case-insensitively, so GITLAB_URL -> gitlab_url.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # A present-but-blank value (e.g. GITLAB_TOKEN=) must fail fast just like a
    # missing one, so both required strings are constrained non-empty.
    gitlab_url: str = Field(min_length=1)
    gitlab_token: str = Field(min_length=1)
    # Pagination safety cap: MAX_PAGES * 100 items. When hit -> truncated=True.
    max_pages: int = Field(10, ge=1)

    @field_validator("gitlab_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        # We append "/api/v4" later; a trailing slash would double up. Guard the
        # slash-only case ("/") so it can't collapse to an empty base URL.
        stripped = value.strip().rstrip("/")
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("gitlab_token")
    @classmethod
    def _require_token(cls, value: str) -> str:
        # A whitespace-only token is an env typo, not a real credential; fail
        # fast at startup like a blank one rather than surfacing a runtime 401.
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


@lru_cache
def get_settings() -> Settings:
    """Return cached settings, or raise ConfigError with a clear message.

    lru_cache only caches successful loads, so a fixed-up environment is
    re-read on the next call.
    """
    try:
        return Settings()  # type: ignore[call-arg]  # values come from the env
    except ValidationError as exc:
        fields = ", ".join(str(err["loc"][0]).upper() for err in exc.errors())
        raise ConfigError(
            f"Invalid or missing configuration ({fields})."
        ) from exc
