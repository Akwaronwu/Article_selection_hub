"""Alembic migration tests: upgrade creates the schema of record.

The authoritative check: after ``upgrade head`` on an empty database, the set
of tables must exactly equal ``Base.metadata`` (models ↔ migration parity).
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

import app.models  # noqa: F401 — registers models
from alembic import command
from app.db import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_db(tmp_path):
    """A fresh SQLite database migrated to head; yields its URL."""
    db_file = tmp_path / "migrated.db"
    url = f"sqlite:///{db_file.as_posix()}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    yield url
    command.downgrade(config, "base")


def test_upgrade_creates_all_model_tables(migrated_db):
    engine = create_engine(migrated_db)
    try:
        actual = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    expected = set(Base.metadata.tables)
    # alembic_version is Alembic's own bookkeeping, not part of the schema.
    actual.discard("alembic_version")
    assert actual == expected, (
        f"Missing from migration: {expected - actual}; "
        f"Extra in migration: {actual - expected}"
    )


def test_alembic_version_recorded(migrated_db):
    engine = create_engine(migrated_db)
    try:
        with engine.connect() as conn:
            from sqlalchemy import text

            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        engine.dispose()
    assert version, "alembic_version has no recorded revision"


def test_downgrade_removes_tables(tmp_path):
    db_file = tmp_path / "downgraded.db"
    url = f"sqlite:///{db_file.as_posix()}"
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(url)
    try:
        remaining = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    # Only alembic's bookkeeping table may remain.
    assert remaining <= {"alembic_version"}