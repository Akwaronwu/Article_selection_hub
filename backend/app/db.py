"""Database engine/session management.

Supports SQLite (development/test) and PostgreSQL (production) through the
same SQLAlchemy ORM layer; the driver is chosen solely by ``SLR_DATABASE_URL``
(see docs/ARCHITECTURE.md §2, §3). Tests use ``configure_engine`` /
``reset_engine`` to point at an isolated temporary database.
"""

from collections.abc import Generator
from contextlib import suppress
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _build_engine(database_url: str) -> Engine:
    kwargs: dict = {"future": True}
    if database_url.startswith("sqlite"):
        # Allow the same connection across TestClient worker threads.
        kwargs["connect_args"] = {"check_same_thread": False}
        # Ensure the parent directory exists for file-backed SQLite databases.
        # Failure is tolerated: the engine still builds and connection errors
        # surface later (e.g. health probe reports the DB as unreachable).
        prefix = "sqlite:///"
        if database_url.startswith(prefix) and len(database_url) > len(prefix):
            db_path = database_url[len(prefix):]
            if db_path not in (":memory:", "") and "?" not in db_path:
                with suppress(OSError):
                    Path(db_path).expanduser().resolve().parent.mkdir(
                        parents=True, exist_ok=True
                    )
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Enforce FK constraints on SQLite so dev/test matches PostgreSQL.

    SQLite ships with foreign_keys=OFF; without this, RESTRICT/CASCADE/
    SET NULL rules would silently not apply outside production.
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def configure_engine(database_url: str) -> Engine:
    """Create (or replace) the process-wide engine for ``database_url``."""
    global _engine, _session_factory
    reset_engine()
    _engine = _build_engine(database_url)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_engine() -> Engine:
    """Return the current engine, creating it lazily from settings."""
    if _engine is None:
        configure_engine(get_settings().database_url)
    assert _engine is not None
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        configure_engine(get_settings().database_url)
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session]:
    """FastAPI dependency yielding a session; always closed after use."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_engine() -> None:
    """Dispose and forget the current engine (used between tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def init_db() -> None:
    """Create tables for all registered models (dev/test bootstrap).

    Production schema management will use Alembic migrations (Phase 2).
    """
    # Importing the models package registers tables on Base.metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(get_engine())


def database_reachable() -> bool:
    """Cheap connectivity probe used by the health endpoint."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — health probe must never raise
        return False
