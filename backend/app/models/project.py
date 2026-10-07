"""Project and membership models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.timeutil import JSON_TYPE, utcnow, uuid4_str

# Project workspace state machine (§4/§59 of the master prompt).
PROJECT_STATUSES = ("draft", "active", "locked", "archived")
PROJECT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"active", "archived"}),
    "active": frozenset({"draft", "locked", "archived"}),
    "locked": frozenset({"active", "archived"}),
    "archived": frozenset({"draft"}),
}


class Project(Base):
    """An SLR / SMS / scoping review workspace."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    research_question: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    review_type: Mapped[str] = mapped_column(String(20), nullable=False)
    objectives: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    settings: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    members: Mapped[list[ProjectMember]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    protocol: Mapped[Protocol | None] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        """Return True when ``current → target`` is a legal status transition."""
        return target in PROJECT_STATUS_TRANSITIONS.get(current, frozenset())


class ProjectMember(Base):
    """Membership of a user in a project, carrying their RBAC role."""

    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_blinded: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")  # noqa: F821
