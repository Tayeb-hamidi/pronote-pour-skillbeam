"""Helpers for asynchronous job state management."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from shared.enums import JobStatus, JobType
from shared.models import Job


def create_job(db: Session, project_id: str, job_type: JobType) -> Job:
    """Create a queued job row."""

    job = Job(
        project_id=project_id,
        job_type=job_type.value,
        status=JobStatus.QUEUED.value,
        progress=0,
        logs_json=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job(
    db: Session,
    job_id: str,
    *,
    status: JobStatus | None = None,
    progress: int | None = None,
    message: str | None = None,
    result_id: str | None = None,
    error_message: str | None = None,
) -> Job:
    """Update job status and append logs."""

    job = db.get(Job, job_id)
    if job is None:
        raise ValueError(f"job {job_id} not found")

    if status is not None:
        job.status = status.value
    if progress is not None:
        job.progress = max(0, min(100, progress))
    if result_id is not None:
        job.result_id = result_id
    if error_message is not None:
        job.error_message = error_message
    if message:
        logs = list(job.logs_json or [])
        logs.append({"at": datetime.now(timezone.utc).isoformat(), "message": message})
        job.logs_json = logs

    db.add(job)
    db.commit()
    db.refresh(job)
    return job
