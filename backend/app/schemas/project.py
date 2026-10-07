"""Pydantic request/response schemas for projects, members, and protocol."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ReviewType = Literal["slr", "sms", "scoping", "rapid", "evidence"]
ProjectStatus = Literal["draft", "active", "locked", "archived"]
MemberRole = Literal["owner", "adjudicator", "reviewer", "assistant", "viewer"]


class ProjectCreate(BaseModel):
    """Payload for ``POST /projects``."""

    title: str = Field(min_length=1, max_length=300)
    review_type: ReviewType = "slr"
    research_question: str | None = Field(default=None, max_length=2000)
    objectives: list[str] | None = None


class ProjectUpdate(BaseModel):
    """Partial payload for ``PATCH /projects/{id}``."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    review_type: ReviewType | None = None
    research_question: str | None = Field(default=None, max_length=2000)
    objectives: list[str] | None = None
    status: ProjectStatus | None = None
    reason: str | None = Field(default=None, max_length=500, description="Audit rationale")


class ProjectOut(BaseModel):
    """Project as returned to its members."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    review_type: str
    status: str
    research_question: str | None = None
    objectives: list[str] | None = None
    owner_id: str
    created_at: datetime
    updated_at: datetime


class MemberAdd(BaseModel):
    """Payload for ``POST /projects/{id}/members``."""

    email: EmailStr
    role: MemberRole = "reviewer"
    is_blinded: bool = False


class MemberUpdate(BaseModel):
    """Payload for ``PATCH /projects/{id}/members/{user_id}``."""

    role: MemberRole | None = None
    is_blinded: bool | None = None
    reason: str | None = Field(default=None, max_length=500)


class MemberOut(BaseModel):
    """Project membership view."""

    user_id: str
    email: EmailStr
    display_name: str
    role: str
    is_blinded: bool
    created_at: datetime


# --- Protocol ---------------------------------------------------------------


class ProtocolUpdate(BaseModel):
    """Partial payload for ``PATCH /projects/{id}/protocol``.

    Only fields present are changed; everything else carries over into the
    new version (§1.5: changes never silently alter other content).
    """

    objectives: list[str] | None = None
    research_questions: list[str] | None = None
    screening_procedure: str | None = Field(default=None, max_length=20000)
    extraction_procedure: str | None = Field(default=None, max_length=20000)
    synthesis_strategy: str | None = Field(default=None, max_length=20000)
    change_note: str | None = Field(default=None, max_length=500)
    reason: str | None = Field(default=None, max_length=500, description="Audit rationale")


class ProtocolVersionOut(BaseModel):
    """One immutable protocol snapshot."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    objectives: list[str] | None = None
    research_questions: list[str] | None = None
    screening_procedure: str | None = None
    extraction_procedure: str | None = None
    synthesis_strategy: str | None = None
    change_note: str | None = None
    created_by: str | None = None
    created_at: datetime


class ProtocolOut(BaseModel):
    """Current protocol state for a project."""

    id: str
    project_id: str
    current_version: int
    is_locked: bool
    locked_at: datetime | None = None
    content: ProtocolVersionOut


class ProtocolVersionSummary(BaseModel):
    """Version listing entry."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    change_note: str | None = None
    created_by: str | None = None
    created_at: datetime
