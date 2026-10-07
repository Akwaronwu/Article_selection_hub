"""Member management: add/update/remove + last-owner invariants."""

from app import db as db_module


def _project_with_second_member(client, make_client, register_user, role="reviewer"):
    """Create a project as Alice and register Bob; return (project_id, bob_client)."""
    register_user(client)
    project_id = client.post(
        "/api/v1/projects", json={"title": "Members test"}
    ).json()["id"]

    bob = make_client()
    register_user(bob, email="bob@example.org", name="Bob")
    added = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "bob@example.org", "role": role},
    )
    assert added.status_code == 201, added.text
    return project_id, bob


def test_add_member_by_email_and_list(client, make_client, register_user):
    project_id, _bob = _project_with_second_member(client, make_client, register_user)

    members = client.get(f"/api/v1/projects/{project_id}/members")
    assert members.status_code == 200
    emails = {m["email"] for m in members.json()}
    assert emails == {"alice@example.org", "bob@example.org"}
    roles = {m["email"]: m["role"] for m in members.json()}
    assert roles["alice@example.org"] == "owner"
    assert roles["bob@example.org"] == "reviewer"


def test_add_unknown_email_returns_404(client, register_user):
    register_user(client)
    project_id = client.post("/api/v1/projects", json={"title": "T"}).json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "ghost@example.org", "role": "reviewer"},
    )
    assert response.status_code == 404
    assert "register" in response.json()["detail"]


def test_duplicate_membership_rejected(client, make_client, register_user):
    project_id, _bob = _project_with_second_member(client, make_client, register_user)
    again = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "bob@example.org", "role": "reviewer"},
    )
    assert again.status_code == 409


def test_non_owner_cannot_manage_members(client, make_client, register_user):
    project_id, bob = _project_with_second_member(client, make_client, register_user)

    # Bob (reviewer) tries to add Dave.
    response = bob.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "alice@example.org", "role": "viewer"},
    )
    assert response.status_code == 403
    assert "members:manage" in response.json()["detail"]


def test_last_owner_cannot_be_demoted_or_removed(client, register_user):
    register_user(client)
    project_id = client.post("/api/v1/projects", json={"title": "Solo"}).json()["id"]
    alice_id = client.get("/api/v1/auth/me").json()["id"]

    demote = client.patch(
        f"/api/v1/projects/{project_id}/members/{alice_id}",
        json={"role": "reviewer"},
    )
    assert demote.status_code == 409
    assert "last owner" in demote.json()["detail"].lower()

    remove = client.delete(f"/api/v1/projects/{project_id}/members/{alice_id}")
    assert remove.status_code == 409


def test_role_change_allowed_with_second_owner(client, make_client, register_user):
    project_id, bob = _project_with_second_member(
        client, make_client, register_user, role="owner"
    )
    bob_id = bob.get("/api/v1/auth/me").json()["id"]

    # Two owners now — demoting one is legal.
    demote = client.patch(
        f"/api/v1/projects/{project_id}/members/{bob_id}",
        json={"role": "reviewer", "reason": "Reassigned"},
    )
    assert demote.status_code == 200
    assert demote.json()["role"] == "reviewer"


def test_remove_member_revokes_access(client, make_client, register_user):
    project_id, bob = _project_with_second_member(client, make_client, register_user)

    # Bob can read the project while a member.
    assert bob.get(f"/api/v1/projects/{project_id}").status_code == 200

    bob_id = bob.get("/api/v1/auth/me").json()["id"]
    assert (
        client.delete(f"/api/v1/projects/{project_id}/members/{bob_id}").status_code == 204
    )

    # Access is gone immediately (404, not 403 — no existence disclosure).
    assert bob.get(f"/api/v1/projects/{project_id}").status_code == 404

    # Audit recorded the removal.
    from sqlalchemy import select

    from app.models import AuditLog

    session = db_module.get_session_factory()()
    try:
        row = session.scalar(
            select(AuditLog).where(AuditLog.action == "member.remove")
        )
        assert row is not None
        assert row.object_before["email"] == "bob@example.org"
    finally:
        session.close()


def test_invalid_role_rejected(client, register_user):
    register_user(client)
    project_id = client.post("/api/v1/projects", json={"title": "T"}).json()["id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "alice@example.org", "role": "dictator"},
    )
    assert response.status_code == 422