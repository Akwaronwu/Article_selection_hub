"""Protocol versioning + lock tests (§47: locked changes create new versions)."""


def _project(client, register_user):
    register_user(client)
    return client.post("/api/v1/projects", json={"title": "Protocol test"}).json()["id"]


def test_project_creation_initialises_protocol_v1(client, register_user):
    project_id = _project(client, register_user)

    response = client.get(f"/api/v1/projects/{project_id}/protocol")
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_version"] == 1
    assert payload["is_locked"] is False
    assert payload["content"]["version"] == 1
    assert payload["content"]["change_note"] == "Initial protocol"


def test_update_creates_new_version_and_preserves_old(client, register_user):
    project_id = _project(client, register_user)

    updated = client.patch(
        f"/api/v1/projects/{project_id}/protocol",
        json={
            "research_questions": ["RQ1: ...", "RQ2: ..."],
            "change_note": "Added RQ2",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["current_version"] == 2
    assert updated.json()["content"]["research_questions"] == ["RQ1: ...", "RQ2: ..."]

    # Old version is still retrievable — history never mutated (§1.5).
    v1 = client.get(f"/api/v1/projects/{project_id}/protocol/versions/1")
    assert v1.status_code == 200
    assert v1.json()["research_questions"] == []

    # Unspecified fields carry over unchanged.
    assert updated.json()["content"]["change_note"] == "Added RQ2"

    versions = client.get(f"/api/v1/projects/{project_id}/protocol/versions")
    assert [v["version"] for v in versions.json()] == [1, 2]


def test_missing_version_returns_404(client, register_user):
    project_id = _project(client, register_user)
    response = client.get(f"/api/v1/projects/{project_id}/protocol/versions/99")
    assert response.status_code == 404


def test_empty_update_rejected(client, register_user):
    project_id = _project(client, register_user)
    response = client.patch(f"/api/v1/projects/{project_id}/protocol", json={})
    assert response.status_code == 422


def test_lock_blocks_edits_until_unlocked(client, register_user):
    project_id = _project(client, register_user)

    locked = client.post(f"/api/v1/projects/{project_id}/protocol/lock")
    assert locked.status_code == 200
    assert locked.json()["is_locked"] is True

    # Double-lock is a conflict.
    assert (
        client.post(f"/api/v1/projects/{project_id}/protocol/lock").status_code == 409
    )

    # Editing a locked protocol is refused.
    blocked = client.patch(
        f"/api/v1/projects/{project_id}/protocol",
        json={"synthesis_strategy": "meta"},
    )
    assert blocked.status_code == 409
    assert "locked" in blocked.json()["detail"].lower()

    # Unlock → edits work again.
    assert (
        client.post(f"/api/v1/projects/{project_id}/protocol/unlock").status_code == 200
    )
    unblocked = client.patch(
        f"/api/v1/projects/{project_id}/protocol",
        json={"synthesis_strategy": "narrative"},
    )
    assert unblocked.status_code == 200
    assert unblocked.json()["current_version"] == 2


def test_unlock_when_not_locked_conflicts(client, register_user):
    project_id = _project(client, register_user)
    assert client.post(f"/api/v1/projects/{project_id}/protocol/unlock").status_code == 409


def test_lock_writes_audit_and_requires_permission(client, make_client, register_user):
    project_id = _project(client, register_user)

    viewer = make_client()
    register_user(viewer, email="viewer@example.org", name="V")
    client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": "viewer@example.org", "role": "viewer"},
    )
    assert (
        viewer.post(f"/api/v1/projects/{project_id}/protocol/lock").status_code == 403
    )
    assert (
        viewer.patch(
            f"/api/v1/projects/{project_id}/protocol", json={"synthesis_strategy": "x"}
        ).status_code
        == 403
    )

    client.post(f"/api/v1/projects/{project_id}/protocol/lock")
    from sqlalchemy import select

    from app import db as db_module
    from app.models import AuditLog

    session = db_module.get_session_factory()()
    try:
        row = session.scalar(select(AuditLog).where(AuditLog.action == "protocol.lock"))
        assert row is not None and row.project_id == project_id
    finally:
        session.close()