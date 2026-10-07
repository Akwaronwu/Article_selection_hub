"""Literature import pipeline (§8, §9 stage 1).

Worker body for ``studies_import`` jobs. Owns its own DB session, runs in
the queue's thread, and *never raises*: any failure marks the job ``failed``
with the reason — a partial import is rolled back, never left half-applied
(§109). Duplicate handling here is **exact-DOI only**; fuzzy/semantic
duplicate detection is Phase 4.
"""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy import select

from app.db import get_session_factory
from app.importers import parse_file
from app.importers.base import normalize_doi, normalize_title
from app.models import AuditLog, ImportBatch, Job, Study, StudyIdentifier, StudySource
from app.timeutil import utcnow

logger = logging.getLogger(__name__)

_MAX_ERROR_SAMPLES = 50


def run_import(
    *,
    job_id: str,
    project_id: str,
    requested_by: str,
    content: bytes,
    filename: str,
    fmt: str,
    source_database: str | None,
) -> None:
    """Parse ``content`` and insert studies for ``project_id`` (all-or-nothing)."""
    session = get_session_factory()()
    try:
        job = session.get(Job, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = utcnow()
        job.progress = 10
        session.commit()

        # Parse (raises -> caught below -> job failed, nothing persisted).
        outcome = parse_file(fmt, content)
        job.progress = 40
        session.commit()

        # Existing DOIs in this project (exact-DOI dedup, stage 1 of §9).
        known: dict[str, str] = {}
        rows = session.execute(
            select(Study.id, Study.doi).where(
                Study.project_id == project_id, Study.doi.is_not(None)
            )
        ).all()
        for study_id, doi in rows:
            canonical = normalize_doi(doi)
            if canonical:
                known.setdefault(canonical, study_id)

        batch = ImportBatch(
            project_id=project_id,
            filename=filename,
            file_hash=hashlib.sha256(content).hexdigest(),
            format=fmt,
            record_count=len(outcome.records),
            source_database=source_database,
            imported_by=requested_by,
        )
        session.add(batch)
        session.flush()

        imported = 0
        skipped = 0
        rejected = 0
        linked_study_ids: set[str] = set()
        errors: list[str] = list(outcome.invalid)

        for record in outcome.records:
            doi = normalize_doi(record.doi)
            if not record.title and not doi:
                rejected += 1
                if len(errors) < _MAX_ERROR_SAMPLES:
                    errors.append("record rejected: neither title nor DOI present")
                continue

            if doi and doi in known:
                skipped += 1
                study_id = known[doi]
            else:
                study = Study(
                    project_id=project_id,
                    title=record.title,
                    normalized_title=normalize_title(record.title),
                    abstract=record.abstract,
                    authors=[a for a in record.authors if a],
                    year=record.year,
                    venue=record.venue,
                    doi=doi,
                    url=record.url,
                    keywords=[k for k in record.keywords if k],
                    affiliations=[a for a in record.affiliations if a],
                    citation_count=record.citation_count,
                    language=record.language,
                    publication_type=record.publication_type,
                    status="IMPORTED",
                )
                session.add(study)
                session.flush()
                study_id = study.id
                if doi:
                    known[doi] = study_id
                    session.add(
                        StudyIdentifier(study_id=study_id, id_type="doi", value=doi)
                    )
                imported += 1

            # Provenance for both new and skipped studies (PRISMA §44).
            if study_id not in linked_study_ids:
                session.add(
                    StudySource(
                        study_id=study_id,
                        import_batch_id=batch.id,
                        source_database=source_database,
                    )
                )
                linked_study_ids.add(study_id)

        counts = {
            "imported": imported,
            "skipped_existing": skipped,
            "rejected": rejected,
            "record_count": len(outcome.records),
            "invalid_entries": outcome.invalid_count,
        }
        batch.result = counts
        batch.errors = (
            {"count": outcome.invalid_count + rejected, "samples": errors[:_MAX_ERROR_SAMPLES]}
            if errors
            else None
        )

        session.add(
            AuditLog(
                action="studies.import",
                entity_type="import_batch",
                entity_id=batch.id,
                project_id=project_id,
                user_id=requested_by,
                object_after={"filename": filename, "format": fmt, **counts},
            )
        )

        job.progress = 90
        session.commit()

        job.status = "done"
        job.progress = 100
        job.result = {"batch_id": batch.id, **counts}
        job.finished_at = utcnow()
        session.commit()
    except Exception as exc:  # noqa: BLE001 — job workers must never raise
        session.rollback()
        logger.exception("import job %s failed", job_id)
        try:
            job = session.get(Job, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:2000]
                job.finished_at = utcnow()
                session.commit()
        except Exception:  # noqa: BLE001
            session.rollback()
            logger.exception("could not mark job %s failed", job_id)
    finally:
        session.close()
