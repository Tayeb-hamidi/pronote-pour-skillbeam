"""Generation service orchestrating content jobs."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from pydantic import BaseModel
from shared.celery_app import create_celery
from shared.correlation import CorrelationIdMiddleware
from shared.db import SessionLocal
from shared.enums import JobType
from shared.jobs import create_job
from shared.logging import configure_logging
from shared.otel import init_otel
from shared.schemas import InternalGenerateRequest
from sqlalchemy.orm import Session

configure_logging()
logger = logging.getLogger(__name__)
celery_app = create_celery("generate-service")

app = FastAPI(title="SkillBeam Generate Service", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)


@app.on_event("startup")
def startup() -> None:
    init_otel("generate-service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "generate"}


class JobLaunchResponse(BaseModel):
    job_id: str


@app.post("/v1/generate", response_model=JobLaunchResponse)
def launch_generate(payload: InternalGenerateRequest) -> JobLaunchResponse:
    with SessionLocal() as db:
        job = _create_generate_job(db=db, project_id=payload.project_id)

    celery_app.send_task(
        "worker.tasks.generate_content",
        kwargs={
            "job_id": job.id,
            "project_id": payload.project_id,
            "content_types": [ct.value for ct in payload.content_types],
            "instructions": payload.instructions,
            "max_items": payload.max_items,
            "language": payload.language,
            "level": payload.level,
            "subject": payload.subject,
            "class_level": payload.class_level,
            "difficulty_target": payload.difficulty_target,
        },
    )
    return JobLaunchResponse(job_id=job.id)


def _create_generate_job(db: Session, project_id: str):
    job = create_job(db=db, project_id=project_id, job_type=JobType.GENERATE)
    logger.info("generate job queued", extra={"job_id": job.id, "project_id": project_id})
    return job
