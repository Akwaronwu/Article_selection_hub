"""Background job queue (§108).

``JobQueue`` is the seam: dev/test use ``InProcessQueue`` (daemon threads);
production can swap in Redis/RQ by registering another implementation —
callers only ever see ``submit(job_id, work)``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Thread

logger = logging.getLogger(__name__)


class JobQueue:
    """Interface for running job work off the request thread."""

    def submit(self, job_id: str, work: Callable[[], None]) -> None:
        """Schedule ``work`` for ``job_id`` (implementation-defined queue)."""
        raise NotImplementedError


class InProcessQueue(JobQueue):
    """Runs each job in a daemon thread — fine for dev, tests, and small teams."""

    def submit(self, job_id: str, work: Callable[[], None]) -> None:
        thread = Thread(
            target=_guarded_run,
            args=(job_id, work),
            name=f"job-{job_id[:8]}",
            daemon=True,
        )
        thread.start()


def _guarded_run(job_id: str, work: Callable[[], None]) -> None:
    """Run ``work``; if it raises anyway, mark the job failed (§109)."""
    try:
        work()
    except Exception as exc:  # noqa: BLE001 — last-resort guard, never crash the process
        logger.exception("job %s crashed", job_id)
        try:
            from app.db import get_session_factory
            from app.models import Job
            from app.timeutil import utcnow

            session = get_session_factory()()
            try:
                job = session.get(Job, job_id)
                if job is not None and job.status not in ("done", "failed"):
                    job.status = "failed"
                    job.error = f"Unhandled error: {exc}"[:2000]
                    job.finished_at = utcnow()
                    session.commit()
            finally:
                session.close()
        except Exception:  # noqa: BLE001
            logger.exception("could not mark job %s as failed", job_id)


_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    """Process-wide queue instance (swapped in tests if needed)."""
    global _queue
    if _queue is None:
        _queue = InProcessQueue()
    return _queue


def set_queue(queue: JobQueue | None) -> None:
    """Replace the global queue (tests / future Redis wiring)."""
    global _queue
    _queue = queue
