"""Project workspace endpoints: CRUD and status management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import ProjectContext, get_current_user, project_context
from app.models import (
    PROJECT_STATUSES,
    Project,
    ProjectMember,
    Protocol,
    ProtocolVersion,
    User,
)
from app.rbac import Permission
from app.schemas.project import MemberOut, ProjectCreate, ProjectOut, ProjectUpdate
from app.services.audit import client_ip, log_action

router = APIRouter(prefix="/projects", tags=["projects"])

# Dependency singletons — one pre-built closure per permission (B008).
require_project_read = Depends(project_context(Permission.PROJECT_READ))
require_project_write = Depends(project_context(Permission.PROJECT_WRITE))
require_project_delete = Depends(project_context(Permission.PROJECT_DELETE))


def _snapshot(project: Project) -> dict:
    """Serializable project state for audit before/after values."""
    return {
        "title": project.title,
        "review_type": project.review_type,
        "status": project.status,
        "research_question": project.research_question,
        "objectives": project.objectives,
    }


def _members_out(db: Session, project_id: str) -> list[MemberOut]:
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at)
    ).all()
    return [
        MemberOut(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=membership.role,
            is_blinded=membership.is_blinded,
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]


@router.get("", response_model=list[ProjectOut], summary="List my projects")
def list_projects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Project]:
    """Return projects the caller is a member of (never others')."""
    rows = db.execute(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.created_at.desc())
    ).scalars()
    return list(rows)


@router.post(
    "",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
def create_project(
    payload: ProjectCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    """Create a project; caller becomes owner; protocol v1 is initialised."""
    project = Project(
        title=payload.title.strip(),
        review_type=payload.review_type,
        research_question=payload.research_question,
        objectives=payload.objectives,
        status="draft",
        owner_id=user.id,
    )
    db.add(project)
    db.flush()

    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    protocol = Protocol(project_id=project.id, current_version=1)
    db.add(protocol)
    db.flush()
    db.add(
        ProtocolVersion(
            protocol_id=protocol.id,
            version=1,
            objectives=project.objectives,
            research_questions=[project.research_question] if project.research_question else [],
            change_note="Initial protocol",
            created_by=user.id,
        )
    )

    log_action(
        db,
        action="project.create",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        user_id=user.id,
        object_after=_snapshot(project),
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut, summary="Get project")
def get_project(
    ctx: ProjectContext = require_project_read,
) -> Project:
    """Return a project (membership required; 404 otherwise)."""
    return ctx.project


@router.patch("/{project_id}", response_model=ProjectOut, summary="Update project")
def update_project(
    payload: ProjectUpdate,
    request: Request,
    ctx: ProjectContext = require_project_write,
    db: Session = Depends(get_db),
) -> Project:
    """Partially update a project; validates the status state machine (§59)."""
    project = ctx.project
    before = _snapshot(project)
    changes = payload.model_dump(exclude_unset=True, exclude={"reason"})

    if "status" in changes and changes["status"] not in PROJECT_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unknown status: {changes['status']}")
    if "status" in changes and not Project.can_transition(project.status, changes["status"]):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Illegal status transition: {project.status} → {changes['status']}",
        )

    for field, value in changes.items():
        setattr(project, field, value)

    log_action(
        db,
        action="project.update",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        user_id=ctx.user.id,
        object_before=before,
        object_after=_snapshot(project),
        reason=payload.reason,
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.commit()
    db.refresh(project)
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
)
def delete_project(
    request: Request,
    ctx: ProjectContext = require_project_delete,
    db: Session = Depends(get_db),
) -> None:
    """Delete a project (owner only); cascades members/protocol, keeps audit."""
    project = ctx.project
    before = _snapshot(project)
    log_action(
        db,
        action="project.delete",
        entity_type="project",
        entity_id=project.id,
        project_id=project.id,
        user_id=ctx.user.id,
        object_before=before,
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.delete(project)
    db.commit()

