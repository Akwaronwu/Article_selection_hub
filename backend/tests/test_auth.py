"""Authentication flow tests (register/login/logout/me) — real HTTP via TestClient."""

from sqlalchemy import select

from app import db as db_module
from app.models import UserSession
from app.security import hash_session_token
from tests.conftest import PASSWORD


def test_register_returns_user_and_sets_cookie(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "Alice@Example.org",
            "password": PASSWORD,
            "display_name": "Alice",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "alice@example.org"  # normalised
    assert "password" not in str(payload).lower() or "password_hash" not in payload
    assert "password_hash" not in payload
    assert "slr_session" in response.cookies


def test_register_rejects_duplicate_email(client, register_user):
    register_user(client)
    again = client.post(
        "/api/v1/auth/register",
        json={"email": "ALICE@example.org", "password": PASSWORD, "display_name": "A2"},
    )
    assert again.status_code == 409


def test_register_enforces_password_policy(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.org", "password": "short", "display_name": "S"},
    )
    assert response.status_code == 422
    assert "10 characters" in response.json()["detail"]


def test_me_requires_authentication(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(client, register_user):
    register_user(client)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.org"


def test_login_success_and_failure(client, register_user):
    register_user(client)

    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.org", "password": "wrong-password-123"},
    )
    assert bad.status_code == 401

    good = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.org", "password": PASSWORD},
    )
    assert good.status_code == 200
    assert good.json()["user"]["email"] == "alice@example.org"
    assert "expires_at" in good.json()


def test_login_unknown_account_indistinguishable_from_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.org", "password": "whatever-1234"},
    )
    assert response.status_code == 401
    # Same detail as a wrong password — no account enumeration.
    assert response.json()["detail"] == "Invalid email or password."


def test_logout_revokes_session(client, register_user):
    register_user(client)
    assert client.get("/api/v1/auth/me").status_code == 200

    out = client.post("/api/v1/auth/logout")
    assert out.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    # Server-side row must be revoked, not just the cookie cleared.
    session = db_module.get_session_factory()()
    try:
        rows = list(session.scalars(select(UserSession)))
    finally:
        session.close()
    assert rows and all(r.revoked_at is not None for r in rows)


def test_session_token_stored_hashed_not_raw(client, register_user):
    """The DB must contain only the SHA-256 digest (SECURITY §1)."""
    register_user(client)
    raw_token = client.cookies.get("slr_session")
    assert raw_token, "session cookie missing"

    session = db_module.get_session_factory()()
    try:
        row = session.scalar(select(UserSession))
    finally:
        session.close()
    assert row is not None
    assert row.token_hash == hash_session_token(raw_token)
    assert row.token_hash != raw_token
    assert len(row.token_hash) == 64


def test_registration_can_be_closed_after_bootstrap(test_settings, tmp_path):
    """With SLR_ALLOW_OPEN_REGISTRATION=false the first user may still sign up."""
    from fastapi.testclient import TestClient

    from app import db as db_module
    from app.main import create_app

    closed = test_settings.model_copy(update={"allow_open_registration": False})
    application = create_app(closed)
    with TestClient(application) as bootstrap_client:
        first = bootstrap_client.post(
            "/api/v1/auth/register",
            json={"email": "root@example.org", "password": PASSWORD, "display_name": "Root"},
        )
        assert first.status_code == 201

        second = bootstrap_client.post(
            "/api/v1/auth/register",
            json={"email": "late@example.org", "password": PASSWORD, "display_name": "Late"},
        )
        assert second.status_code == 403
        assert "closed" in second.json()["detail"].lower()
    db_module.reset_engine()