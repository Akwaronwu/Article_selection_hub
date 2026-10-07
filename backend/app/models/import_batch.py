"""Import batch and search-strategy models (§8, §45–46)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.timeutil import JSON_TYPE, utcnow, uuid4_str


class ImportBatch(Base):
    """One literature-file import into a project."""

    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_database: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    errors: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    imported_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Search(Base):
    """A documented database search (§45): query, date, result count."""

    __tablename__ = "searches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    database_name: Mapped[str] = mapped_column(String(100), nullable=False)
    search_string: Mapped[str] = mapped_column(Text, nullable=False)
    search_string_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_searched: Mapped[date | None] = mapped_column(Date, nullable=True)
    filters: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    export_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    export_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
