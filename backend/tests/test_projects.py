"""Project lifecycle tests: create/read/update/delete + authorization."""

from sqlalchemy import select

from app import db as db_module
from app.models import AuditLog, ProjectMember, Protocol


def _create_project(client, title="AI for Secure SE"):
    return client.post(
        "/api/v1/projects",
        json={
            "title": title,
            "review_type": "slr",
            "research_question": "RQ1: How is AI used?",
        },
    )


def test_create_project_bootstraps_owner_member_and_protocol(client, register_user):
    register_user(client)
    response = _create_project(client)

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "AI for Secure SE"
    assert payload["status"] == "draft"
    assert payload["review_type"] == "slr"

    session = db_module.get_session_factory()()
    try:
        project_id = payload["id"]
        membership = session.scalar(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
        )
        assert membership is not None and membership.role == "owner"
        protocol = session.scalar(select(Protocol).where(Protocol.project_id == project_id))
        assert protocol is not None and protocol.current_version == 1
        audit = session.scalar(select(AuditLog).where(AuditLog.action == "project.create"))
        assert audit is not None and audit.entity_id == project_id
    finally:
        session.close()


def test_project_requires_authentication(client):
    assert client.get("/api/v1/projects").status_code == 401
    assert _create_project(client).status_code == 401


def test_list_projects_shows_only_my_projects(client, make_client, register_user):
    register_user(client)
    _create_project(client, title="Alice Project")

    other = make_client()
    register_user(other, email="bob@example.org", name="Bob")
    _create_project(other, title="Bob Project")

    alice_view = client.get("/api/v1/projects")
    bob_view = other.get("/api/v1/projects")

    assert [p["title"] for p in alice_view.json()] == ["Alice Project"]
    assert [p["title"] for p in bob_view.json()] == ["Bob Project"]


def test_non_member_gets_404_not_403(client, make_client, register_user):
    """Anti-IDOR: foreign project existence must not be revealed (SECURITY §2)."""
    register_user(client)
    project_id = _create_project(client).json()["id"]

    stranger = make_client()
    register_user(stranger, email="eve@example.org", name="Eve")

    assert stranger.get(f"/api/v1/projects/{project_id}").status_code == 404
    assert (
        stranger.patch(f"/api/v1/projects/{project_id}", json={"title": "hacked"}).status_code
        == 404
    )


def test_update_project_writes_audit_with_before_after(client, register_user):
    register_user(client)
    project_id = _create_project(client).json()["id"]

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"title": "Renamed Review", "reason": "Scope clarified"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed Review"

    session = db_module.get_session_factory()()
    try:
        audit = session.scalar(
            select(AuditLog)
            .where(AuditLog.action == "project.update")
            .order_by(AuditLog.created_at.desc())
        )
        assert audit is not None
        assert audit.object_before["title"] == "AI for Secure SE"
        assert audit.object_after["title"] == "Renamed Review"
        assert audit.reason == "Scope clarified"
        assert audit.user_id is not None
    finally:
        session.close()


def test_status_state_machine_enforced(client, register_user):
    register_user(client)
    project_id = _create_project(client).json()["id"]

    # draft → active is legal
    ok = client.patch(f"/api/v1/projects/{project_id}", json={"status": "active"})
    assert ok.status_code == 200

    # active → draft is legal; draft → locked is ILLEGAL (only active/archived).
    client.patch(f"/api/v1/projects/{project_id}", json={"status": "draft"})
    illegal = client.patch(f"/api/v1/projects/{project_id}", json={"status": "locked"})
    assert illegal.status_code == 409
    assert "Illegal status transition" in illegal.json()["detail"]


def test_delete_project_owner_only_and_cascades(client, make_client, register_user):
    register_user(client)
    project_id = _create_project(client).json()["id"]

    # A reviewer cannot delete (no project:delete permission).
    helper = make_client()
    register_user(helper, email="carol@example.org", name="Carol")
    client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "carol@example.org", "role": "reviewer"},
    )
    assert helper.delete(f"/api/v1/projects/{project_id}").status_code == 403

    # Owner can.
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404

    # Membership cascaded away (SQLite FK enforcement is on).
    session = db_module.get_session_factory()()
    try:
        leftover = session.scalars(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
        ).all()
        assert leftover == []
        # Audit row survives deletion (entity_id retains the deleted id).
        audit = session.scalar(
            select(AuditLog).where(AuditLog.action == "project.delete")
        )
        assert audit is not None and audit.entity_id == project_id
    finally:
        session.close()


def test_unauthorized_role_cannot_update(client, make_client, register_user):
    register_user(client)
    project_id = _create_project(client).json()["id"]

    viewer = make_client()
    register_user(viewer, email="dan@example.org", name="Dan")
    client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "dan@example.org", "role": "viewer"},
    )

    response = viewer.patch(f"/api/v1/projects/{project_id}", json={"title": "nope"})
    assert response.status_code == 403
    assert "project:write" in response.json()["detail"]
    # But reading is allowed for viewers.
    assert viewer.get(f"/api/v1/projects/{project_id}").status_code == 200


def test_invalid_review_type_rejected(client, register_user):
    register_user(client)
    response = client.post(
        "/api/v1/projects", json={"title": "Bad type", "review_type": "nonsense"}
    )
    assert response.status_code == 422


def test_sensitive_values_never_in_responses(client, register_user):
    """Responses must never leak password hashes or the test password."""
    from tests.conftest import PASSWORD

    register_user(client)
    me = client.get("/api/v1/auth/me").text
    assert "password_hash" not in me
    assert "$argon2" not in me
    project = _create_project(client).text
    assert PASSWORD not in project
