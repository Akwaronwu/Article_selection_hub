"""Database layer tests: engine lifecycle and a real SQL round-trip."""

import pytest
from sqlalchemy import text

from app import db as db_module


@pytest.fixture(autouse=True)
def _clean_engine():
    """Guarantee no engine leaks between tests."""
    db_module.reset_engine()
    yield
    db_module.reset_engine()


def test_engine_created_lazily_from_settings(tmp_path):
    url = f"sqlite:///{(tmp_path / 'lazy.db').as_posix()}"

    db_module.configure_engine(url)
    engine = db_module.get_engine()

    assert engine.url.render_as_string(hide_password=False).startswith("sqlite:")


def test_sql_roundtrip(tmp_path):
    db_module.configure_engine(f"sqlite:///{(tmp_path / 'roundtrip.db').as_posix()}")
    engine = db_module.get_engine()

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY, note TEXT)"))
        conn.execute(text("INSERT INTO probe (note) VALUES ('evidence')"))

    with engine.connect() as conn:
        row = conn.execute(text("SELECT note FROM probe")).scalar_one()

    assert row == "evidence"


def test_get_db_yields_and_closes_session(tmp_path):
    db_module.configure_engine(f"sqlite:///{(tmp_path / 'session.db').as_posix()}")

    gen = db_module.get_db()
    session = next(gen)
    assert session.bind is not None
    with pytest.raises(StopIteration):
        next(gen)  # dependency closes the session on exit


def test_database_reachable_false_after_bad_engine(tmp_path):
    """Probe must return False (not raise) when connections fail."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    db_module.configure_engine(f"sqlite:///{(blocker / 'db.sqlite').as_posix()}")

    assert db_module.database_reachable() is False
