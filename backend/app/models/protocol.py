"""Review protocol and its immutable version history (§47, §1.5).

A change to a protocol always inserts a new ``ProtocolVersion`` row; the
previous content remains retrievable forever.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.timeutil import JSON_TYPE, utcnow, uuid4_str


class Protocol(Base):
    """The mutable pointer to a project's protocol (current version + lock)."""

    __tablename__ = "protocols"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="protocol")  # noqa: F821
    versions: Mapped[list[ProtocolVersion]] = relationship(
        back_populates="protocol",
        cascade="all, delete-orphan",
        order_by="ProtocolVersion.version",
    )

    @property
    def is_locked(self) -> bool:
        """True when the protocol is locked (§47)."""
        return self.locked_at is not None


class ProtocolVersion(Base):
    """One immutable snapshot of the protocol's content."""

    __tablename__ = "protocol_versions"
    __table_args__ = (UniqueConstraint("protocol_id", "version", name="uq_protocol_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    protocol_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("protocols.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    objectives: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True)
    research_questions: Mapped[list | None] = mapped_column(JSON_TYPE, nullable=True)
    screening_procedure: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_procedure: Mapped[str | None] = mapped_column(Text, nullable=True)
    synthesis_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    protocol: Mapped[Protocol] = relationship(back_populates="versions")
