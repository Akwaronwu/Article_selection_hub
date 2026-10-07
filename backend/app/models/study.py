"""Study (literature record) models and the §59 screening state machine."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.timeutil import JSON_TYPE, utcnow, uuid4_str

# Screening pipeline states (master prompt §59). Transition enforcement
# arrives with the screening pipeline (Phase 5).
STUDY_STATUSES = (
    "IMPORTED",
    "DUPLICATE_CHECK",
    "TITLE_ABSTRACT_PENDING",
    "TITLE_ABSTRACT_SCREENED",
    "FULL_TEXT_PENDING",
    "FULL_TEXT_SCREENED",
    "QUALITY_ASSESSMENT",
    "EXTRACTION",
    "VERIFICATION",
    "INCLUDED",
    "EXCLUDED",
)


class Study(Base):
    """One literature record inside a project."""

    __tablename__ = "studies"
    __table_args__ = (
        Index("ix_studies_project_doi", "project_id", "doi"),
        Index("ix_studies_project_title", "project_id", "normalized_title"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    normalized_title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(500), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    keywords: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    affiliations: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    publication_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="IMPORTED")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )


class StudyIdentifier(Base):
    """External identifiers (DOI, PMID, arXiv…) for a study."""

    __tablename__ = "study_identifiers"
    __table_args__ = (
        UniqueConstraint("study_id", "id_type", "value", name="uq_study_id_type_value"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("studies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    id_type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)


class StudySource(Base):
    """Provenance: which import batch (and later, which search) found a study."""

    __tablename__ = "study_sources"
    __table_args__ = (
        UniqueConstraint("study_id", "import_batch_id", name="uq_study_batch"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("studies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    import_batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("import_batches.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    search_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("searches.id", ondelete="SET NULL"), nullable=True
    )
    source_database: Mapped[str | None] = mapped_column(String(100), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
