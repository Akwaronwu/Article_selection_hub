"""Shared FastAPI dependencies: authentication and project authorization.

Authorization model (docs/SECURITY.md §2):
  * No session → 401 ``not_authenticated``
  * Project missing OR caller not a member → 404 ``project_not_found``
    (prevents IDOR: existence of foreign projects is never revealed)
  * Member lacking the required permission → 403 ``forbidden``
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.models import Project, ProjectMember, User, UserSession
from app.rbac import Permission, has_permission
from app.security import hash_session_token


@dataclass(frozen=True)
class ProjectContext:
    """Resolved (user, project, membership) triple for authorized endpoints."""

    user: User
    project: Project
    membership: ProjectMember

    @property
    def role(self) -> str:
        """Caller's role in this project."""
        return self.membership.role


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_settings_from_app(request: Request) -> Settings:
    """Settings bound to the running app instance (test-injectable)."""
    return request.app.state.settings


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the session cookie.

    Raises 401 when the cookie is missing, unknown, revoked, expired, or the
    user account is deactivated.
    """
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _unauthenticated()

    token_hash = hash_session_token(token)
    session_row = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
    )
    if session_row is None or not session_row.is_valid:
        raise _unauthenticated()

    user = db.get(User, session_row.user_id)
    if user is None or not user.is_active:
        raise _unauthenticated()
    return user


def project_context(permission: Permission):
    """Dependency factory: require membership with ``permission`` in ``{project_id}``."""

    def dependency(
        project_id: str,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> ProjectContext:
        project = db.get(Project, project_id)
        membership = None
        if project is not None:
            membership = db.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user.id,
                )
            )
        if project is None or membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        if not has_permission(membership.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{membership.role}' lacks permission '{permission.value}'",
            )
        return ProjectContext(user=user, project=project, membership=membership)

    return dependency
