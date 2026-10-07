"""Audit logging service (§48).

Every significant mutation calls ``log_action`` within the same transaction
as the change itself, so an audit row can never exist without its change (or
vice versa) for committed data.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    object_before: dict | None = None,
    object_after: dict | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Append one audit row (caller's transaction owns commit/rollback)."""
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        project_id=project_id,
        user_id=user_id,
        object_before=object_before,
        object_after=object_after,
        reason=reason,
        ip_address=ip_address,
    )
    db.add(entry)
    return entry


def client_ip(request_ip: str | None) -> str | None:
    """Truncate a client IP to the column's storage size."""
    return request_ip[:45] if request_ip else None
