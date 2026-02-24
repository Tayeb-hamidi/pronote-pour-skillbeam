"""Export service orchestrating export jobs and plugin metadata."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from shared.celery_app import create_celery
from shared.correlation import CorrelationIdMiddleware
from shared.db import SessionLocal
from shared.enums import JobType
from shared.jobs import create_job
from shared.logging import configure_logging
from shared.otel import init_otel
from shared.schemas import InternalExportRequest
from sqlalchemy.orm import Session

from app.exporters.registry import get_exporters

configure_logging()
logger = logging.getLogger(__name__)
celery_app = create_celery("export-service")

app = FastAPI(title="SkillBeam Export Service", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


@app.on_event("startup")
def startup() -> None:
    init_otel("export-service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "export"}


class JobLaunchResponse(BaseModel):
    job_id: str


@app.get("/v1/export/formats")
def list_formats() -> dict[str, list[str]]:
    return {"formats": sorted(get_exporters().keys())}


@app.post("/v1/export", response_model=JobLaunchResponse)
def launch_export(payload: InternalExportRequest) -> JobLaunchResponse:
    exporters = get_exporters()
    if payload.format.value not in exporters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format"
        )

    with SessionLocal() as db:
        job = _create_export_job(db=db, project_id=payload.project_id)

    celery_app.send_task(
        "worker.tasks.export_content",
        kwargs={
            "job_id": job.id,
            "project_id": payload.project_id,
            "format_name": payload.format.value,
            "options": payload.options,
        },
    )
    return JobLaunchResponse(job_id=job.id)


def _create_export_job(db: Session, project_id: str):
    job = create_job(db=db, project_id=project_id, job_type=JobType.EXPORT)
    logger.info("export job queued", extra={"job_id": job.id, "project_id": project_id})
    return job
