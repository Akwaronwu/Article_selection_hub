"""Protocol endpoints: read, versioned updates, lock/unlock (§47).

Every content edit creates a new immutable ``ProtocolVersion``; previous
versions remain retrievable. Locking freezes edits (409 until unlocked).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import ProjectContext, project_context
from app.models import Protocol, ProtocolVersion
from app.rbac import Permission
from app.schemas.project import ProtocolOut, ProtocolUpdate, ProtocolVersionOut
from app.services.audit import client_ip, log_action
from app.timeutil import utcnow

router = APIRouter(prefix="/projects/{project_id}/protocol", tags=["protocol"])

# Dependency singletons — one pre-built closure per permission (B008).
require_project_read = Depends(project_context(Permission.PROJECT_READ))
require_protocol_edit = Depends(project_context(Permission.PROTOCOL_EDIT))
require_protocol_lock = Depends(project_context(Permission.PROTOCOL_LOCK))

_CONTENT_FIELDS = (
    "objectives",
    "research_questions",
    "screening_procedure",
    "extraction_procedure",
    "synthesis_strategy",
)


def _load_protocol(db: Session, project_id: str) -> Protocol:
    protocol = db.scalar(select(Protocol).where(Protocol.project_id == project_id))
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return protocol


def _current_version(db: Session, protocol: Protocol) -> ProtocolVersion:
    version = db.scalar(
        select(ProtocolVersion).where(
            ProtocolVersion.protocol_id == protocol.id,
            ProtocolVersion.version == protocol.current_version,
        )
    )
    if version is None:
        raise HTTPException(status_code=500, detail="Current protocol version missing")
    return version


def _protocol_out(protocol: Protocol, content: ProtocolVersion) -> ProtocolOut:
    return ProtocolOut(
        id=protocol.id,
        project_id=protocol.project_id,
        current_version=protocol.current_version,
        is_locked=protocol.is_locked,
        locked_at=protocol.locked_at,
        content=ProtocolVersionOut.model_validate(content),
    )


@router.get("", response_model=ProtocolOut, summary="Get current protocol")
def get_protocol(
    ctx: ProjectContext = require_project_read,
    db: Session = Depends(get_db),
) -> ProtocolOut:
    """Return the current protocol version and lock state."""
    protocol = _load_protocol(db, ctx.project.id)
    return _protocol_out(protocol, _current_version(db, protocol))


@router.patch("", response_model=ProtocolOut, summary="Update protocol (new version)")
def update_protocol(
    payload: ProtocolUpdate,
    request: Request,
    ctx: ProjectContext = require_protocol_edit,
    db: Session = Depends(get_db),
) -> ProtocolOut:
    """Apply partial edits as a *new* protocol version (§1.5, §47).

    Unspecified fields carry over unchanged. Locked protocols reject edits
    with 409 until an owner unlocks them.
    """
    protocol = _load_protocol(db, ctx.project.id)
    if protocol.is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Protocol is locked; unlock it before editing",
        )

    current = _current_version(db, protocol)
    changes = payload.model_dump(exclude_unset=True, exclude={"change_note", "reason"})
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")

    new_values: dict = {}
    for field in _CONTENT_FIELDS:
        new_values[field] = changes.get(field, getattr(current, field))

    new_version = ProtocolVersion(
        protocol_id=protocol.id,
        version=protocol.current_version + 1,
        change_note=payload.change_note,
        created_by=ctx.user.id,
        **new_values,
    )
    protocol.current_version = new_version.version
    db.add(new_version)

    log_action(
        db,
        action="protocol.update",
        entity_type="protocol",
        entity_id=protocol.id,
        project_id=ctx.project.id,
        user_id=ctx.user.id,
        object_before={"version": current.version},
        object_after={"version": new_version.version, "fields": sorted(changes)},
        reason=payload.reason or payload.change_note,
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.commit()
    db.refresh(protocol)
    return _protocol_out(protocol, new_version)


@router.get(
    "/versions",
    response_model=list[ProtocolVersionOut],
    summary="List protocol versions",
)
def list_versions(
    ctx: ProjectContext = require_project_read,
    db: Session = Depends(get_db),
) -> list[ProtocolVersion]:
    """Return all protocol versions (oldest first)."""
    protocol = _load_protocol(db, ctx.project.id)
    return list(
        db.scalars(
            select(ProtocolVersion)
            .where(ProtocolVersion.protocol_id == protocol.id)
            .order_by(ProtocolVersion.version)
        )
    )


@router.get(
    "/versions/{version}",
    response_model=ProtocolVersionOut,
    summary="Get a protocol version",
)
def get_version(
    version: int,
    ctx: ProjectContext = require_project_read,
    db: Session = Depends(get_db),
) -> ProtocolVersion:
    """Return one immutable protocol snapshot (404 when absent)."""
    protocol = _load_protocol(db, ctx.project.id)
    row = db.scalar(
        select(ProtocolVersion).where(
            ProtocolVersion.protocol_id == protocol.id,
            ProtocolVersion.version == version,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Protocol version not found")
    return row


@router.post("/lock", response_model=ProtocolOut, summary="Lock the protocol")
def lock_protocol(
    request: Request,
    ctx: ProjectContext = require_protocol_lock,
    db: Session = Depends(get_db),
) -> ProtocolOut:
    """Freeze the protocol against edits (owner/adjudicator permission)."""
    protocol = _load_protocol(db, ctx.project.id)
    if protocol.is_locked:
        raise HTTPException(status_code=409, detail="Protocol is already locked")

    protocol.locked_at = utcnow()
    log_action(
        db,
        action="protocol.lock",
        entity_type="protocol",
        entity_id=protocol.id,
        project_id=ctx.project.id,
        user_id=ctx.user.id,
        object_after={"locked_at": protocol.locked_at.isoformat()},
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.commit()
    db.refresh(protocol)
    return _protocol_out(protocol, _current_version(db, protocol))


@router.post("/unlock", response_model=ProtocolOut, summary="Unlock the protocol")
def unlock_protocol(
    request: Request,
    ctx: ProjectContext = require_protocol_lock,
    db: Session = Depends(get_db),
) -> ProtocolOut:
    """Lift the protocol lock (owner/adjudicator permission)."""
    protocol = _load_protocol(db, ctx.project.id)
    if not protocol.is_locked:
        raise HTTPException(status_code=409, detail="Protocol is not locked")

    log_action(
        db,
        action="protocol.unlock",
        entity_type="protocol",
        entity_id=protocol.id,
        project_id=ctx.project.id,
        user_id=ctx.user.id,
        object_before={"locked_at": protocol.locked_at.isoformat()},
        ip_address=client_ip(request.client.host if request.client else None),
    )
    protocol.locked_at = None
    db.commit()
    db.refresh(protocol)
    return _protocol_out(protocol, _current_version(db, protocol))
