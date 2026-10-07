"""RBAC permission matrix — pure unit tests, exhaustive (§56–57)."""

from app.rbac import Permission, Role, has_permission, permissions_for, valid_role

ALL_PERMISSIONS = set(Permission)


def test_owner_has_everything_except_nothing():
    owner_perms = permissions_for(Role.OWNER)
    # Owner is the only role that may delete a project and manage members.
    assert Permission.PROJECT_DELETE in owner_perms
    assert Permission.MEMBERS_MANAGE in owner_perms
    assert owner_perms >= permissions_for(Role.ADJUDICATOR)


def test_viewer_is_read_only():
    viewer_perms = permissions_for(Role.VIEWER)
    assert viewer_perms == frozenset({Permission.PROJECT_READ})


def test_reviewer_cannot_write_project_or_manage_members():
    assert not has_permission(Role.REVIEWER, Permission.PROJECT_WRITE)
    assert not has_permission(Role.REVIEWER, Permission.MEMBERS_MANAGE)
    assert not has_permission(Role.REVIEWER, Permission.PROJECT_DELETE)
    # But can screen and verify extractions.
    assert has_permission(Role.REVIEWER, Permission.SCREENING_DECIDE)
    assert has_permission(Role.REVIEWER, Permission.EXTRACTION_VERIFY)


def test_adjudicator_can_adjudicate_but_not_delete_or_manage_members():
    assert has_permission(Role.ADJUDICATOR, Permission.SCREENING_ADJUDICATE)
    assert has_permission(Role.ADJUDICATOR, Permission.PROTOCOL_EDIT)
    assert not has_permission(Role.ADJUDICATOR, Permission.PROJECT_DELETE)
    assert not has_permission(Role.ADJUDICATOR, Permission.MEMBERS_MANAGE)


def test_assistant_is_read_extraction_and_import():
    assert permissions_for(Role.ASSISTANT) == frozenset(
        {Permission.PROJECT_READ, Permission.EXTRACTION_VERIFY, Permission.STUDIES_IMPORT}
    )


def test_unknown_role_fails_closed():
    """Unknown/role-injection attempts must grant nothing."""
    assert not has_permission("superuser", Permission.PROJECT_READ)
    assert not has_permission("", Permission.PROJECT_READ)
    assert not has_permission("OWNER ", Permission.PROJECT_DELETE)
    assert permissions_for("hacker") == frozenset()


def test_every_role_grants_project_read():
    for role in Role:
        assert has_permission(role, Permission.PROJECT_READ), role


def test_valid_role_parser():
    assert valid_role("owner")
    assert valid_role("viewer")
    assert not valid_role("root")
    assert not valid_role("")


def test_permission_values_are_strings():
    """Permission values are used in API error messages; keep them stable."""
    assert Permission.PROJECT_READ.value == "project:read"
    assert Permission.SCREENING_ADJUDICATE.value == "screening:adjudicate"
    assert len(ALL_PERMISSIONS) == len(set(p.value for p in Permission))
