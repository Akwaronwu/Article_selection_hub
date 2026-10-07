"""Health endpoint integration tests (real app + real temp database)."""


def test_health_returns_ok_with_reachable_database(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "reachable"
    assert payload["environment"] == "test"
    assert payload["service"] == "AI-Assisted SLR Platform"


def test_unknown_route_returns_404(client):
    response = client.get("/api/v1/definitely-not-a-route")
    assert response.status_code == 404


def test_openapi_schema_generated(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/health" in schema["paths"]


def test_health_degrades_without_database(tmp_path):
    """A broken DB path must yield 503 + degraded status, not a crash."""
    from fastapi.testclient import TestClient

    from app import db as db_module
    from app.config import Settings
    from app.main import create_app

    # A *file* where the SQLite directory should be → all connections fail.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{(blocker / 'db.sqlite').as_posix()}",
        cors_origins=["http://testserver"],
        auto_create_tables=False,
    )
    application = create_app(settings)
    try:
        with TestClient(application) as failing_client:
            response = failing_client.get("/api/v1/health")
        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "degraded"
        assert payload["database"] == "unreachable"
    finally:
        db_module.reset_engine()
