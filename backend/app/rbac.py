"""Role-Based Access Control (§56–57).

Pure functions — no FastAPI/DB dependencies — so the permission matrix can be
unit-tested exhaustively. Roles: owner > adjudicator > reviewer > assistant >
viewer, evaluated per project membership.

Permissions:
  project:read      view project workspace and its studies
  project:write     edit project metadata, criteria, schemas
  project:delete    delete the project
  members:manage    add/remove/change project members
  protocol:edit     edit protocol (creates a new version)
  protocol:lock     lock/unlock the protocol
  audit:read        read the audit log
  screening:decide  record screening decisions
  screening:adjudicate  resolve reviewer conflicts
  extraction:verify verify extracted data
  studies:import    import literature files into the project
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Project member roles (most to least privileged)."""

    OWNER = "owner"
    ADJUDICATOR = "adjudicator"
    REVIEWER = "reviewer"
    ASSISTANT = "assistant"
    VIEWER = "viewer"


class Permission(StrEnum):
    """Named capabilities checked at endpoints."""

    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"
    PROJECT_DELETE = "project:delete"
    MEMBERS_MANAGE = "members:manage"
    PROTOCOL_EDIT = "protocol:edit"
    PROTOCOL_LOCK = "protocol:lock"
    AUDIT_READ = "audit:read"
    SCREENING_DECIDE = "screening:decide"
    SCREENING_ADJUDICATE = "screening:adjudicate"
    EXTRACTION_VERIFY = "extraction:verify"
    STUDIES_IMPORT = "studies:import"


_READ = frozenset({Permission.PROJECT_READ})
_PROJECT_ADMIN = frozenset(
    {
        Permission.PROJECT_WRITE,
        Permission.MEMBERS_MANAGE,
        Permission.PROTOCOL_EDIT,
        Permission.PROTOCOL_LOCK,
        Permission.AUDIT_READ,
        Permission.SCREENING_ADJUDICATE,
        Permission.EXTRACTION_VERIFY,
        Permission.STUDIES_IMPORT,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: _READ | _PROJECT_ADMIN | frozenset(
        {Permission.PROJECT_DELETE, Permission.SCREENING_DECIDE}
    ),
    Role.ADJUDICATOR: _READ | frozenset(
        {
            Permission.PROTOCOL_EDIT,
            Permission.AUDIT_READ,
            Permission.SCREENING_ADJUDICATE,
            Permission.SCREENING_DECIDE,
            Permission.EXTRACTION_VERIFY,
            Permission.STUDIES_IMPORT,
        }
    ),
    Role.REVIEWER: _READ
    | frozenset({Permission.SCREENING_DECIDE, Permission.EXTRACTION_VERIFY}),
    # Research assistants commonly perform literature imports.
    Role.ASSISTANT: _READ
    | frozenset({Permission.EXTRACTION_VERIFY, Permission.STUDIES_IMPORT}),
    Role.VIEWER: _READ,
}


def has_permission(role: str | Role, permission: Permission) -> bool:
    """Return True when ``role`` grants ``permission``.

    Unknown roles grant nothing (fail closed).
    """
    try:
        parsed = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS[parsed]


def valid_role(role: str) -> bool:
    """Return True when ``role`` is a known role name."""
    try:
        Role(role)
    except ValueError:
        return False
    return True


def permissions_for(role: str | Role) -> frozenset[Permission]:
    """Return the full permission set for ``role`` (empty for unknown roles)."""
    try:
        parsed = Role(role)
    except ValueError:
        return frozenset()
    return ROLE_PERMISSIONS[parsed]
