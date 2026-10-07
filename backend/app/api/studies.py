"""Study endpoints: browse, detail, and background import (§8, §108)."""

from __future__ import annotations

from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import ProjectContext, project_context
from app.importers import SUPPORTED_FORMATS, UnsupportedFormatError, detect_format
from app.jobs import get_queue
from app.models import Job, Study
from app.rbac import Permission
from app.schemas.study import ImportAccepted, StudyOut, StudyPage
from app.services.import_service import run_import

router = APIRouter(prefix="/projects/{project_id}/studies", tags=["studies"])

# Dependency singletons — one pre-built closure per permission (B008).
require_project_read = Depends(project_context(Permission.PROJECT_READ))
require_studies_import = Depends(project_context(Permission.STUDIES_IMPORT))


@router.get("", response_model=StudyPage, summary="List studies")
def list_studies(
    ctx: ProjectContext = require_project_read,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: Literal[
        "IMPORTED",
        "DUPLICATE_CHECK",
        "TITLE_ABSTRACT_PENDING",
        "TITLE_ABSTRACT_SCREENED",
        "FULL_TEXT_PENDING",
        "FULL_TEXT_SCREENED",
        "QUALITY_ASSESSMENT",
        "EXTRACTION",
        "VERIFICATION",
        "INCLUDED",
        "EXCLUDED",
    ] | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=200, description="Search title/abstract/DOI"),
) -> StudyPage:
    """Paginated studies for this project with optional status/text filters."""
    conditions = [Study.project_id == ctx.project.id]
    if status_filter is not None:
        conditions.append(Study.status == status_filter)
    if q:
        pattern = f"%{q.lower()}%"
        conditions.append(
            func.lower(Study.title).like(pattern)
            | func.lower(Study.doi).like(pattern)
            | func.lower(Study.abstract).like(pattern)
        )

    total = db.scalar(select(func.count()).select_from(Study).where(*conditions)) or 0
    rows = list(
        db.scalars(
            select(Study)
            .where(*conditions)
            .order_by(Study.created_at, Study.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return StudyPage(items=rows, total=total, page=page, page_size=page_size)


@router.post(
    "/import",
    response_model=ImportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import a literature file (background job)",
)
async def import_studies(
    request: Request,
    file: UploadFile = File(...),
    source_database: str = Form("upload"),
    format: Literal["ris", "bibtex", "csv", "doi_list"] | None = Form(None),
    ctx: ProjectContext = require_studies_import,
    db: Session = Depends(get_db),
) -> ImportAccepted:
    """Queue a background import; returns ``job_id`` for polling (§108).

    Synchronous validation (size, format) fails fast with 4xx; parsing and
    insertion happen in the job so large files never block the API.
    """
    settings = request.app.state.settings
    content = await file.read(settings.max_import_bytes + 1)
    if len(content) > settings.max_import_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_import_bytes}-byte import limit",
        )
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    filename = file.filename or "upload"
    try:
        fmt = format or detect_format(filename, content)
        if fmt not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(f"Unsupported format '{fmt}'")
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = Job(
        project_id=ctx.project.id,
        kind="studies_import",
        status="queued",
        payload={
            "filename": filename,
            "format": fmt,
            "source_database": source_database[:100],
        },
        created_by=ctx.user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    get_queue().submit(
        job.id,
        lambda: run_import(
            job_id=job.id,
            project_id=ctx.project.id,
            requested_by=ctx.user.id,
            content=content,
            filename=filename,
            fmt=fmt,
            source_database=source_database[:100],
        ),
    )
    return ImportAccepted(job_id=job.id, status=job.status)


@router.get("/{study_id}", response_model=StudyOut, summary="Get a study")
def get_study(
    study_id: str,
    ctx: ProjectContext = require_project_read,
    db: Session = Depends(get_db),
) -> Study:
    """Return one study (membership required; 404 otherwise)."""
    study = db.scalar(
        select(Study).where(Study.id == study_id, Study.project_id == ctx.project.id)
    )
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    return study
