"""Configuration tests: environment-driven settings, no hard-coded values."""

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_defaults_for_development():
    settings = Settings(_env_file=None, environment="development")

    assert settings.environment == "development"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url.startswith("sqlite:")
    assert settings.auto_create_tables is True


def test_environment_prefix_is_slr(monkeypatch):
    """Variables are read from the SLR_* namespace only."""
    monkeypatch.setenv("SLR_APP_NAME", "Renamed Service")
    monkeypatch.setenv("SLR_DATABASE_URL", "postgresql+psycopg://user:pass@db/slr")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Renamed Service"
    assert settings.database_url == "postgresql+psycopg://user:pass@db/slr"


def test_foreign_env_vars_are_ignored(monkeypatch):
    """Unrelated environment variables must not leak into settings."""
    monkeypatch.setenv("DATABASE_URL", "should-be-ignored")

    settings = Settings(_env_file=None)

    assert settings.database_url != "should-be-ignored"


def test_invalid_environment_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="staging")


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
