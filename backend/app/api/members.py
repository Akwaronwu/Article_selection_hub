"""Project membership management (owner-only via members:manage)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import ProjectContext, project_context
from app.models import ProjectMember, User
from app.rbac import Permission
from app.schemas.project import MemberAdd, MemberOut, MemberUpdate
from app.services.audit import client_ip, log_action

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])

# Dependency singletons — one pre-built closure per permission (B008).
require_project_read = Depends(project_context(Permission.PROJECT_READ))
require_members_manage = Depends(project_context(Permission.MEMBERS_MANAGE))


def _get_member(db: Session, project_id: str, user_id: str) -> ProjectMember:
    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


def _owner_count(db: Session, project_id: str) -> int:
    """Number of owner-role memberships in a project (guard for last owner)."""
    return (
        db.scalar(
            select(func.count())
            .select_from(ProjectMember)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == "owner",
            )
        )
        or 0
    )


@router.get("", response_model=list[MemberOut], summary="List members")
def list_members(
    ctx: ProjectContext = require_project_read,
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    """Return all members of the project."""
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == ctx.project.id)
        .order_by(ProjectMember.created_at)
    ).all()
    return [
        MemberOut(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=member.role,
            is_blinded=member.is_blinded,
            created_at=member.created_at,
        )
        for member, user in rows
    ]


@router.post(
    "",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member",
)
def add_member(
    payload: MemberAdd,
    request: Request,
    ctx: ProjectContext = require_members_manage,
    db: Session = Depends(get_db),
) -> MemberOut:
    """Add an existing user to the project by email (owner only)."""
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="No account with that email; ask them to register first.",
        )

    existing = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == ctx.project.id,
            ProjectMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="User is already a member")

    member = ProjectMember(
        project_id=ctx.project.id,
        user_id=user.id,
        role=payload.role,
        is_blinded=payload.is_blinded,
    )
    db.add(member)
    log_action(
        db,
        action="member.add",
        entity_type="project_member",
        entity_id=member.id,
        project_id=ctx.project.id,
        user_id=ctx.user.id,
        object_after={"user_id": user.id, "email": user.email, "role": member.role},
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.commit()
    db.refresh(member)
    return MemberOut(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=member.role,
        is_blinded=member.is_blinded,
        created_at=member.created_at,
    )


@router.patch("/{user_id}", response_model=MemberOut, summary="Update a member")
def update_member(
    user_id: str,
    payload: MemberUpdate,
    request: Request,
    ctx: ProjectContext = require_members_manage,
    db: Session = Depends(get_db),
) -> MemberOut:
    """Change a member's role and/or blinding flag (owner only).

    The last remaining owner can neither be demoted nor blinded, so a project
    can never become ownerless.
    """
    member = _get_member(db, ctx.project.id, user_id)
    before = {"role": member.role, "is_blinded": member.is_blinded}
    changes = payload.model_dump(exclude_unset=True, exclude={"reason"})

    demoting = "role" in changes and member.role == "owner" and changes["role"] != "owner"
    if demoting and _owner_count(db, ctx.project.id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot demote the last owner of a project",
        )

    for field, value in changes.items():
        setattr(member, field, value)

    log_action(
        db,
        action="member.update",
        entity_type="project_member",
        entity_id=member.id,
        project_id=ctx.project.id,
        user_id=ctx.user.id,
        object_before=before,
        object_after={"role": member.role, "is_blinded": member.is_blinded},
        reason=payload.reason,
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.commit()
    db.refresh(member)

    user = db.get(User, member.user_id)
    return MemberOut(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=member.role,
        is_blinded=member.is_blinded,
        created_at=member.created_at,
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member",
)
def remove_member(
    user_id: str,
    request: Request,
    ctx: ProjectContext = require_members_manage,
    db: Session = Depends(get_db),
) -> None:
    """Remove a member (owner only); refuses to remove the last owner."""
    member = _get_member(db, ctx.project.id, user_id)
    if member.role == "owner" and _owner_count(db, ctx.project.id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove the last owner of a project",
        )

    user = db.get(User, member.user_id)
    log_action(
        db,
        action="member.remove",
        entity_type="project_member",
        entity_id=member.id,
        project_id=ctx.project.id,
        user_id=ctx.user.id,
        object_before={"user_id": user.id, "email": user.email, "role": member.role},
        ip_address=client_ip(request.client.host if request.client else None),
    )
    db.delete(member)
    db.commit()

