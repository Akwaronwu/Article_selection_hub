"""Shared pytest fixtures.

Every test runs against an isolated temporary SQLite database: the app is
built with explicit settings and the global engine is reset after each test,
so tests can never touch development data (docs/ARCHITECTURE.md §10).
"""

from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.config import Settings
from app.main import create_app

#: Default test password (satisfies the 10-character policy).
PASSWORD = "correct-horse-battery-staple"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_bytes() -> Callable[[str], bytes]:
    """Load a file from tests/fixtures as bytes."""

    def _load(name: str) -> bytes:
        return (FIXTURES_DIR / name).read_bytes()

    return _load


@pytest.fixture
def poll_job(client) -> Callable[[str], dict]:
    """Poll a job endpoint until it reaches a terminal state (done/failed)."""
    import time as _time

    def _poll(job_id: str, timeout: float = 15.0) -> dict:
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            response = client.get(f"/api/v1/jobs/{job_id}")
            assert response.status_code == 200, response.text
            data = response.json()
            if data["status"] in ("done", "failed"):
                return data
            _time.sleep(0.05)
        raise AssertionError(f"job {job_id} did not finish within {timeout}s")

    return _poll


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    """Settings pointing at a throwaway SQLite file in pytest's tmp dir."""
    return Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        cors_origins=["http://testserver"],
    )


@pytest.fixture
def application(test_settings):
    """The FastAPI app under test (no lifespan yet)."""
    return create_app(test_settings)


@pytest.fixture
def client(application) -> Generator[TestClient]:
    """Primary client; runs lifespan (DB bootstrap); resets engine after."""
    with TestClient(application) as test_client:
        yield test_client
    db_module.reset_engine()


@pytest.fixture
def make_client(application, client) -> Generator[Callable[[], TestClient]]:
    """Factory for extra clients with isolated cookie jars.

    Depends on ``client`` so the lifespan (engine + tables) ran first;
    extra clients intentionally skip lifespan to avoid re-configuring the
    global engine mid-test.
    """
    created: list[TestClient] = []

    def _make() -> TestClient:
        extra = TestClient(application)
        created.append(extra)
        return extra

    yield _make

    for extra in created:
        extra.close()


@pytest.fixture
def register_user() -> Callable[..., dict]:
    """Register a user via the API; returns the response JSON (asserts 201)."""

    def _register(
        client: TestClient,
        email: str = "alice@example.org",
        password: str = PASSWORD,
        name: str = "Alice",
    ) -> dict:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "display_name": name},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _register
