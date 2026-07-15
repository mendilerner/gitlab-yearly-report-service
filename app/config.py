"""Application configuration, loaded from environment variables.

Only the env vars mandated by the spec are read: GITLAB_URL, GITLAB_TOKEN,
plus the project-defined MAX_PAGES pagination cap. Missing required values fail
fast with a clear message (assignment requirement: missing token -> clear
startup failure).
"""

from functools import lru_cache

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    # env vars are matched case-insensitively, so GITLAB_URL -> gitlab_url.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gitlab_url: str
    gitlab_token: str
    # Pagination safety cap: MAX_PAGES * 100 items. When hit -> truncated=True.
    max_pages: int = 50

    @field_validator("gitlab_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        # We append "/api/v4" later; a trailing slash would double up.
        return value.rstrip("/")


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
