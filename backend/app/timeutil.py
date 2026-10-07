"""Shared SQLAlchemy column helpers.

All timestamps are stored as *naive UTC* datetimes for consistency across
SQLite (dev/test) and PostgreSQL (production).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB


def uuid4_str() -> str:
    """Generate a string UUID usable as a primary key."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (see module docstring)."""
    return datetime.now(UTC).replace(tzinfo=None)


# JSON on SQLite/Postgres-dev, JSONB on PostgreSQL in production (§3 schema doc).
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
