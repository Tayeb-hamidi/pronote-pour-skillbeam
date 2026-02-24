"""Ingestion service orchestrating parse jobs."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from pydantic import BaseModel
from shared.celery_app import create_celery
from shared.config import get_settings
from shared.correlation import CorrelationIdMiddleware
from shared.db import SessionLocal
from shared.enums import JobType
from shared.jobs import create_job
from shared.logging import configure_logging
from shared.otel import init_otel
from shared.schemas import InternalIngestRequest
from sqlalchemy.orm import Session

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
celery_app = create_celery("ingest-service")

app = FastAPI(title="SkillBeam Ingest Service", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


@app.on_event("startup")
def startup() -> None:
    init_otel("ingest-service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ingest"}


class JobLaunchResponse(BaseModel):
    job_id: str


@app.post("/v1/ingest", response_model=JobLaunchResponse)
def launch_ingest(payload: InternalIngestRequest) -> JobLaunchResponse:
    with SessionLocal() as db:
        job = _create_ingest_job(db=db, project_id=payload.project_id)

    celery_app.send_task(
        "worker.tasks.parse_source",
        kwargs={
            "job_id": job.id,
            "project_id": payload.project_id,
            "source_asset_id": payload.source_asset_id,
        },
    )
    return JobLaunchResponse(job_id=job.id)


def _create_ingest_job(db: Session, project_id: str):
    job = create_job(db=db, project_id=project_id, job_type=JobType.INGEST)
    logger.info("ingest job queued", extra={"job_id": job.id, "project_id": project_id})
    return job
