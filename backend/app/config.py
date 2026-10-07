"""Environment-driven application settings.

No hard-coded keys, URLs, model names, or thresholds anywhere else in the
codebase (see docs/ARCHITECTURE.md §10). All variables use the ``SLR_`` prefix
and may be provided via process environment or a ``.env`` file.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

VALID_ENVIRONMENTS = ("development", "test", "production")


class Settings(BaseSettings):
    """Application configuration resolved from the environment."""

    app_name: str = "AI-Assisted SLR Platform"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", pattern="^(development|test|production)$")
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/slr.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    docs_enabled: bool = True
    auto_create_tables: bool = True

    # --- Sessions & registration (Phase 2) ---
    session_cookie_name: str = "slr_session"
    session_ttl_hours: int = Field(default=168, ge=1)  # 7 days
    allow_open_registration: bool = True

    # --- Literature import (Phase 3) ---
    max_import_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)

    model_config = SettingsConfigDict(
        env_prefix="SLR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings()
