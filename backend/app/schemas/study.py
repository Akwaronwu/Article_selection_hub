"""Pydantic schemas for studies, import jobs, and job status."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ImportFormat = Literal["ris", "bibtex", "csv", "doi_list"]


class StudyOut(BaseModel):
    """Public view of one literature record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    keywords: list[str] = Field(default_factory=list)
    language: str | None = None
    publication_type: str | None = None
    citation_count: int | None = None
    status: str
    created_at: datetime


class StudyPage(BaseModel):
    """Paginated study listing."""

    items: list[StudyOut]
    total: int
    page: int
    page_size: int


class ImportAccepted(BaseModel):
    """Response to a successful import submission (202)."""

    job_id: str
    status: str = "queued"


class JobOut(BaseModel):
    """Background job status for polling."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: str
    status: str
    progress: int
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
