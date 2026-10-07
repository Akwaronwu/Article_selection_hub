"""Background job status endpoint (§108)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Job, ProjectMember, User
from app.schemas.study import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut, summary="Get job status")
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    """Poll a job's status; requires membership in the job's project.

    Non-members receive 404 (anti-IDOR: job existence is not disclosed).
    """
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    membership = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == job.project_id,
            ProjectMember.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
