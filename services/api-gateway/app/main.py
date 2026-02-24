"""SkillBeam API Gateway (BFF)."""

from __future__ import annotations

from collections import Counter
import hashlib
import logging
import re
from uuid import uuid4
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import httpx
from shared.auth import create_access_token, get_current_user_id
from shared.config import get_settings
from shared.correlation import CorrelationIdMiddleware
from shared.db import get_db
from shared.enums import ItemType, ProjectState, SourceType
from shared.logging import configure_logging
from shared.models import (
    ContentSet,
    ExportJob,
    Item,
    Job,
    NormalizedDocument,
    Project,
    PronoteImportRun,
    QuestionBankVersion,
    SourceAsset,
    User,
)
from shared.otel import init_otel
from shared.rate_limit import rate_limit_dependency
from shared.schemas import (
    AnalyticsResponse,
    AuthLoginRequest,
    AuthTokenResponse,
    ContentItemOut,
    ContentSetResponse,
    ContentSetUpdateRequest,
    DownloadResponse,
    ExportRequest,
    GenerateRequest,
    IngestRequest,
    InternalExportRequest,
    InternalGenerateRequest,
    InternalIngestRequest,
    JobResponse,
    ProjectCreateRequest,
    ProjectResponse,
    PronoteImportRequest,
    PronoteImportResponse,
    QualityIssue,
    QualityPreviewResponse,
    QuestionBankVersionCreateRequest,
    QuestionBankVersionResponse,
    SourceDocumentResponse,
    SourceDocumentUpdateRequest,
    SourceInitRequest,
    SourceInitResponse,
)
from shared.storage import ObjectStorage
from sqlalchemy import select
from sqlalchemy.orm import Session

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
storage = ObjectStorage()

ALLOWED_DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/markdown",
    "image/png",
    "image/jpeg",
    "image/jpg",
}
CLOZE_PLACEHOLDER_PATTERN = re.compile(
    r"(_{2,}|\{\{blank\}\}|\[blank\]|\(blank\)|\{:MULTICHOICE:[^}]+\})",
    flags=re.IGNORECASE,
)

app = FastAPI(title="SkillBeam API Gateway", version="0.1.0")
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_otel("api-gateway")
    try:
        storage.ensure_bucket()
    except Exception:
        logger.exception("object storage init failed during startup")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


auth_router = APIRouter(prefix="/v1/auth", tags=["auth"])
v1_router = APIRouter(prefix="/v1", tags=["v1"], dependencies=[Depends(rate_limit_dependency)])


@auth_router.post("/token", response_model=AuthTokenResponse)
def issue_token(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    """Issue JWT for a known user.

    Demo implementation for local environments.
    """

    hashed = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        user = User(email=payload.email, password_hash=hashed)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.password_hash != hashed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, ttl = create_access_token(user.id)
    return AuthTokenResponse(access_token=token, expires_in=ttl)


@v1_router.post("/projects", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = Project(user_id=user_id, title=payload.title, state=ProjectState.DRAFT.value)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@v1_router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = _get_user_project(db=db, project_id=project_id, user_id=user_id)
    return ProjectResponse.model_validate(project)


@v1_router.post("/projects/{project_id}/sources", response_model=SourceInitResponse)
def init_source(
    project_id: str,
    payload: SourceInitRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SourceInitResponse:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)

    if payload.source_type == SourceType.DOCUMENT:
        _validate_document_payload(payload)
        key = f"uploads/{project_id}/{uuid4()}_{payload.filename}"
        upload_url = storage.generate_upload_url(key)
        source = SourceAsset(
            project_id=project_id,
            source_type=payload.source_type.value,
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            object_key=key,
            status="upload_initialized",
            metadata_json={
                "enable_ocr": payload.enable_ocr,
                "enable_table_extraction": payload.enable_table_extraction,
                "smart_cleaning": payload.smart_cleaning,
            },
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return SourceInitResponse(asset_id=source.id, upload_url=upload_url, object_key=key)

    _validate_non_document_payload(payload)

    source = SourceAsset(
        project_id=project_id,
        source_type=payload.source_type.value,
        raw_text=payload.raw_text,
        status="uploaded",
        metadata_json={
            "link_url": payload.link_url,
            "topic": payload.topic,
            "subject": payload.subject,
            "class_level": payload.class_level,
            "difficulty_target": payload.difficulty_target,
            "learning_goal": payload.learning_goal,
            "enable_ocr": payload.enable_ocr,
            "enable_table_extraction": payload.enable_table_extraction,
            "smart_cleaning": payload.smart_cleaning,
        },
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return SourceInitResponse(asset_id=source.id)


@v1_router.post("/projects/{project_id}/ingest", response_model=dict)
async def launch_ingest(
    project_id: str,
    payload: IngestRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    body = InternalIngestRequest(project_id=project_id, source_asset_id=payload.source_asset_id)
    data = await _post_internal(f"{settings.ingest_service_url}/v1/ingest", body.model_dump())
    return {"job_id": data["job_id"]}


@v1_router.post("/projects/{project_id}/generate", response_model=dict)
async def launch_generate(
    project_id: str,
    payload: GenerateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    body = InternalGenerateRequest(
        project_id=project_id,
        content_types=payload.content_types,
        instructions=payload.instructions,
        max_items=payload.max_items,
        language=payload.language,
        level=payload.level,
        subject=payload.subject,
        class_level=payload.class_level,
        difficulty_target=payload.difficulty_target,
    )
    data = await _post_internal(
        f"{settings.generate_service_url}/v1/generate", body.model_dump(mode="json")
    )
    return {"job_id": data["job_id"]}


@v1_router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
) -> JobResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    project = _get_user_project(db=db, project_id=job.project_id, user_id=user_id)
    if project.id != job.project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse.model_validate(job)


@v1_router.get("/projects/{project_id}/content", response_model=ContentSetResponse)
def get_project_content(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ContentSetResponse:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    content_set = db.scalar(
        select(ContentSet)
        .where(ContentSet.project_id == project_id)
        .order_by(ContentSet.created_at.desc())
    )
    if content_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No generated content")
    items = db.scalars(
        select(Item).where(Item.content_set_id == content_set.id).order_by(Item.position.asc())
    ).all()
    return _build_content_set_response(content_set=content_set, items=items)


@v1_router.put("/projects/{project_id}/content", response_model=ContentSetResponse)
def update_project_content(
    project_id: str,
    payload: ContentSetUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ContentSetResponse:
    project = _get_user_project(db=db, project_id=project_id, user_id=user_id)

    content_set = None
    if payload.content_set_id:
        content_set = db.get(ContentSet, payload.content_set_id)
    if content_set is None:
        content_set = db.scalar(
            select(ContentSet)
            .where(ContentSet.project_id == project_id)
            .order_by(ContentSet.created_at.desc())
        )
    if content_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No content set to update"
        )

    existing_items = db.scalars(select(Item).where(Item.content_set_id == content_set.id)).all()
    for existing in existing_items:
        db.delete(existing)

    new_items: list[Item] = []
    for index, item_payload in enumerate(payload.items):
        item = Item(
            content_set_id=content_set.id,
            item_type=item_payload.item_type.value,
            prompt=item_payload.prompt,
            correct_answer=item_payload.correct_answer,
            distractors_json=item_payload.distractors,
            answer_options_json=item_payload.answer_options,
            tags_json=item_payload.tags,
            difficulty=item_payload.difficulty,
            feedback=item_payload.feedback,
            source_reference=item_payload.source_reference,
            position=index,
        )
        db.add(item)
        new_items.append(item)

    project.state = ProjectState.REVIEWED.value
    db.add(project)
    _create_question_bank_version(
        db=db,
        project_id=project_id,
        content_set=content_set,
        items=new_items,
        source="auto_save",
        label="Version auto (edition)",
    )
    db.commit()
    db.refresh(content_set)
    return _build_content_set_response(content_set=content_set, items=new_items)


@v1_router.get("/projects/{project_id}/quality-preview", response_model=QualityPreviewResponse)
def get_quality_preview(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> QualityPreviewResponse:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    content_set = db.scalar(
        select(ContentSet)
        .where(ContentSet.project_id == project_id)
        .order_by(ContentSet.created_at.desc())
    )
    if content_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No generated content")

    items = db.scalars(
        select(Item).where(Item.content_set_id == content_set.id).order_by(Item.position.asc())
    ).all()
    return _compute_quality_preview(
        project_id=project_id, content_set_id=content_set.id, items=items
    )


@v1_router.get(
    "/projects/{project_id}/question-bank/versions",
    response_model=list[QuestionBankVersionResponse],
)
def list_question_bank_versions(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[QuestionBankVersionResponse]:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    rows = db.scalars(
        select(QuestionBankVersion)
        .where(QuestionBankVersion.project_id == project_id)
        .order_by(QuestionBankVersion.version_number.desc(), QuestionBankVersion.created_at.desc())
    ).all()
    return [QuestionBankVersionResponse.model_validate(row) for row in rows]


@v1_router.post(
    "/projects/{project_id}/question-bank/versions", response_model=QuestionBankVersionResponse
)
def create_question_bank_version(
    project_id: str,
    payload: QuestionBankVersionCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> QuestionBankVersionResponse:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    content_set = _resolve_content_set(
        db=db, project_id=project_id, content_set_id=payload.content_set_id
    )
    if content_set is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No content set to version"
        )
    items = db.scalars(
        select(Item).where(Item.content_set_id == content_set.id).order_by(Item.position.asc())
    ).all()
    version = _create_question_bank_version(
        db=db,
        project_id=project_id,
        content_set=content_set,
        items=items,
        source="manual",
        label=(payload.label or "").strip() or "Version enseignant",
    )
    db.commit()
    db.refresh(version)
    return QuestionBankVersionResponse.model_validate(version)


@v1_router.post(
    "/projects/{project_id}/question-bank/versions/{version_id}/restore",
    response_model=ContentSetResponse,
)
def restore_question_bank_version(
    project_id: str,
    version_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ContentSetResponse:
    project = _get_user_project(db=db, project_id=project_id, user_id=user_id)
    version = db.scalar(
        select(QuestionBankVersion).where(
            QuestionBankVersion.id == version_id,
            QuestionBankVersion.project_id == project_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    content_set = _resolve_content_set(
        db=db, project_id=project_id, content_set_id=version.content_set_id
    )
    if content_set is None:
        content_set = ContentSet(
            project_id=project_id, status="reviewed", language="fr", level="intermediate"
        )
        db.add(content_set)
        db.flush()

    existing = db.scalars(select(Item).where(Item.content_set_id == content_set.id)).all()
    for row in existing:
        db.delete(row)

    restored_items: list[Item] = []
    for idx, row in enumerate(version.snapshot_json or []):
        if not isinstance(row, dict):
            continue
        item_type = str(row.get("item_type") or ItemType.MCQ.value)
        prompt = str(row.get("prompt") or "").strip()
        if not prompt:
            continue
        item = Item(
            content_set_id=content_set.id,
            item_type=item_type,
            prompt=prompt,
            correct_answer=(
                row.get("correct_answer") if isinstance(row.get("correct_answer"), str) else None
            ),
            distractors_json=_coerce_str_list(row.get("distractors")),
            answer_options_json=_coerce_str_list(row.get("answer_options")),
            tags_json=_coerce_str_list(row.get("tags")),
            difficulty=str(row.get("difficulty") or "medium"),
            feedback=(row.get("feedback") if isinstance(row.get("feedback"), str) else None),
            source_reference=(
                row.get("source_reference")
                if isinstance(row.get("source_reference"), str)
                else None
            ),
            position=idx,
        )
        db.add(item)
        restored_items.append(item)

    project.state = ProjectState.REVIEWED.value
    db.add(project)
    db.commit()
    db.refresh(content_set)
    return _build_content_set_response(content_set=content_set, items=restored_items)


@v1_router.post("/projects/{project_id}/pronote/import", response_model=PronoteImportResponse)
def import_pronote_xml(
    project_id: str,
    payload: PronoteImportRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PronoteImportResponse:
    project = _get_user_project(db=db, project_id=project_id, user_id=user_id)
    parsed_items, type_breakdown = _parse_pronote_xml(payload.xml_content)
    if not parsed_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune question exploitable dans le XML Pronote",
        )

    target_content_set: ContentSet | None
    if payload.replace_current_content:
        target_content_set = _resolve_content_set(db=db, project_id=project_id, content_set_id=None)
    else:
        target_content_set = None

    if target_content_set is None:
        target_content_set = ContentSet(
            project_id=project_id, status="reviewed", language="fr", level="intermediate"
        )
        db.add(target_content_set)
        db.flush()
    else:
        existing = db.scalars(
            select(Item).where(Item.content_set_id == target_content_set.id)
        ).all()
        for row in existing:
            db.delete(row)

    for idx, row in enumerate(parsed_items):
        db.add(
            Item(
                content_set_id=target_content_set.id,
                item_type=row["item_type"],
                prompt=row["prompt"],
                correct_answer=row.get("correct_answer"),
                distractors_json=row.get("distractors", []),
                answer_options_json=row.get("answer_options", []),
                tags_json=row.get("tags", []),
                difficulty=row.get("difficulty", "medium"),
                feedback=row.get("feedback"),
                source_reference=row.get("source_reference", f"section:{idx + 1}"),
                position=idx,
            )
        )

    run = PronoteImportRun(
        project_id=project_id,
        source_filename=payload.source_filename,
        imported_items_count=len(parsed_items),
        stats_json={
            "type_breakdown": dict(type_breakdown),
            "source_hash": hashlib.sha256(payload.xml_content.encode("utf-8")).hexdigest(),
        },
    )
    db.add(run)
    project.state = ProjectState.REVIEWED.value
    db.add(project)
    db.commit()
    db.refresh(run)
    db.refresh(target_content_set)
    return PronoteImportResponse(
        project_id=project_id,
        imported_items_count=len(parsed_items),
        content_set_id=target_content_set.id,
        type_breakdown=dict(type_breakdown),
        import_run_id=run.id,
    )


@v1_router.get("/projects/{project_id}/analytics", response_model=AnalyticsResponse)
def get_project_analytics(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AnalyticsResponse:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    latest_content_set = _resolve_content_set(db=db, project_id=project_id, content_set_id=None)
    items = (
        db.scalars(
            select(Item)
            .where(Item.content_set_id == latest_content_set.id)
            .order_by(Item.position.asc())
        ).all()
        if latest_content_set
        else []
    )
    by_item_type = Counter(item.item_type for item in items)
    by_difficulty = Counter((item.difficulty or "medium") for item in items)

    jobs = db.scalars(select(Job).where(Job.project_id == project_id)).all()
    jobs_by_status = Counter(job.status for job in jobs)
    exports = db.scalars(select(ExportJob).where(ExportJob.project_id == project_id)).all()
    export_by_format = Counter(row.format for row in exports)
    version_count = len(
        db.scalars(
            select(QuestionBankVersion).where(QuestionBankVersion.project_id == project_id)
        ).all()
    )
    import_count = len(
        db.scalars(select(PronoteImportRun).where(PronoteImportRun.project_id == project_id)).all()
    )

    return AnalyticsResponse(
        project_id=project_id,
        total_items=len(items),
        latest_content_set_id=latest_content_set.id if latest_content_set else None,
        by_item_type=dict(by_item_type),
        by_difficulty=dict(by_difficulty),
        jobs_by_status=dict(jobs_by_status),
        export_by_format=dict(export_by_format),
        question_bank_versions=version_count,
        pronote_import_runs=import_count,
    )


@v1_router.get("/projects/{project_id}/document", response_model=SourceDocumentResponse)
def get_project_document(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SourceDocumentResponse:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    document = db.scalar(
        select(NormalizedDocument)
        .where(NormalizedDocument.project_id == project_id)
        .order_by(NormalizedDocument.created_at.desc())
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No normalized document")
    return SourceDocumentResponse(
        document_id=document.id,
        project_id=document.project_id,
        plain_text=document.plain_text,
        metadata=document.metadata_json or {},
        updated_at=document.updated_at,
    )


@v1_router.put("/projects/{project_id}/document", response_model=SourceDocumentResponse)
def update_project_document(
    project_id: str,
    payload: SourceDocumentUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SourceDocumentResponse:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)
    document = db.scalar(
        select(NormalizedDocument)
        .where(NormalizedDocument.project_id == project_id)
        .order_by(NormalizedDocument.created_at.desc())
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No normalized document")

    normalized_text = payload.plain_text.strip()
    if not normalized_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="plain_text cannot be empty"
        )

    document.plain_text = normalized_text
    document.sections_json = _build_sections_for_text(normalized_text)
    db.add(document)
    db.commit()
    db.refresh(document)
    return SourceDocumentResponse(
        document_id=document.id,
        project_id=document.project_id,
        plain_text=document.plain_text,
        metadata=document.metadata_json or {},
        updated_at=document.updated_at,
    )


@v1_router.post("/projects/{project_id}/export", response_model=dict)
async def launch_export(
    project_id: str,
    payload: ExportRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    _get_user_project(db=db, project_id=project_id, user_id=user_id)

    body = InternalExportRequest(
        project_id=project_id, format=payload.format, options=payload.options
    )
    data = await _post_internal(
        f"{settings.export_service_url}/v1/export", body.model_dump(mode="json")
    )
    return {"job_id": data["job_id"]}


@v1_router.get("/exports/{export_id}/download", response_model=DownloadResponse)
def get_export_download(
    export_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> DownloadResponse:
    export_job = db.get(ExportJob, export_id)
    if not export_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    _get_user_project(db=db, project_id=export_job.project_id, user_id=user_id)
    if not export_job.object_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Export artifact not ready"
        )

    url = storage.generate_download_url(
        export_job.object_key,
        filename=export_job.filename,
        mime_type=export_job.mime_type,
    )
    return DownloadResponse(export_id=export_id, url=url)


app.include_router(auth_router)
app.include_router(v1_router)


def _coerce_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(entry).strip() for entry in value if str(entry).strip()]


def _resolve_content_set(
    db: Session, project_id: str, content_set_id: str | None
) -> ContentSet | None:
    if content_set_id:
        return db.scalar(
            select(ContentSet).where(
                ContentSet.id == content_set_id, ContentSet.project_id == project_id
            )
        )
    return db.scalar(
        select(ContentSet)
        .where(ContentSet.project_id == project_id)
        .order_by(ContentSet.created_at.desc())
    )


def _serialize_item(item: Item) -> ContentItemOut:
    return ContentItemOut(
        id=item.id,
        item_type=item.item_type,
        prompt=item.prompt,
        correct_answer=item.correct_answer,
        distractors=item.distractors_json or [],
        answer_options=item.answer_options_json or [],
        tags=item.tags_json or [],
        difficulty=item.difficulty,
        feedback=item.feedback,
        source_reference=item.source_reference,
        position=item.position,
    )


def _build_content_set_response(content_set: ContentSet, items: list[Item]) -> ContentSetResponse:
    return ContentSetResponse(
        content_set_id=content_set.id,
        project_id=content_set.project_id,
        status=content_set.status,
        language=content_set.language,
        level=content_set.level,
        items=[_serialize_item(item) for item in items],
    )


def _snapshot_item(item: Item) -> dict[str, object]:
    return {
        "item_type": item.item_type,
        "prompt": item.prompt,
        "correct_answer": item.correct_answer,
        "distractors": list(item.distractors_json or []),
        "answer_options": list(item.answer_options_json or []),
        "tags": list(item.tags_json or []),
        "difficulty": item.difficulty,
        "feedback": item.feedback,
        "source_reference": item.source_reference,
        "position": item.position,
    }


def _next_version_number(db: Session, project_id: str) -> int:
    rows = db.scalars(
        select(QuestionBankVersion.version_number).where(
            QuestionBankVersion.project_id == project_id
        )
    ).all()
    return (max(rows) + 1) if rows else 1


def _create_question_bank_version(
    *,
    db: Session,
    project_id: str,
    content_set: ContentSet,
    items: list[Item],
    source: str,
    label: str,
) -> QuestionBankVersion:
    version = QuestionBankVersion(
        project_id=project_id,
        content_set_id=content_set.id,
        version_number=_next_version_number(db, project_id),
        label=label,
        source=source,
        snapshot_json=[_snapshot_item(item) for item in items],
    )
    db.add(version)
    return version


def _split_expected_answers(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    chunks = re.split(r"\s*(?:\|\||;;|;|\n)\s*", raw_value)
    deduped: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        cleaned = chunk.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _split_expected_answers_keep_duplicates(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    chunks = re.split(r"\s*(?:\|\||;;|;|\n)\s*", raw_value)
    values: list[str] = []
    for chunk in chunks:
        cleaned = chunk.strip()
        if cleaned:
            values.append(cleaned)
    return values


def _count_cloze_holes(prompt: str) -> int:
    if not prompt.strip():
        return 0
    return len(CLOZE_PLACEHOLDER_PATTERN.findall(prompt))


def _extract_cloze_answers_from_prompt(prompt: str) -> tuple[str, list[str], list[str]]:
    token_pattern = re.compile(r"\{:MULTICHOICE:([^}]*)\}", flags=re.IGNORECASE)
    expected: list[str] = []
    distractors: list[str] = []

    def parse_token_options(token_body: str) -> None:
        for fragment in token_body.split("#~"):
            match = re.match(r"%\s*([-+]?\d+(?:\.\d+)?)\s*%(.*)", fragment.strip())
            if not match:
                continue
            try:
                fraction = float(match.group(1))
            except ValueError:
                fraction = 0.0
            value = match.group(2).strip()
            if not value:
                continue
            if fraction > 0:
                expected.append(value)
            else:
                distractors.append(value)

    for token_match in token_pattern.finditer(prompt):
        parse_token_options(token_match.group(1))

    prompt_without_tokens = token_pattern.sub("____", prompt).strip()

    deduped_expected = _split_expected_answers_keep_duplicates(" || ".join(expected))
    deduped_distractors = _split_expected_answers(" || ".join(distractors))
    return prompt_without_tokens, deduped_expected, deduped_distractors


def _compute_quality_preview(
    project_id: str, content_set_id: str, items: list[Item]
) -> QualityPreviewResponse:
    issues: list[QualityIssue] = []
    by_type = Counter(item.item_type for item in items)
    by_difficulty = Counter((item.difficulty or "medium") for item in items)
    score = 100

    for index, item in enumerate(items, start=1):
        prompt = (item.prompt or "").strip()
        correct = (item.correct_answer or "").strip()
        distractors = [
            value.strip() for value in (item.distractors_json or []) if value and value.strip()
        ]
        answer_options = [
            value.strip() for value in (item.answer_options_json or []) if value and value.strip()
        ]
        has_source_reference = bool((item.source_reference or "").strip())

        if len(prompt) < 16:
            score -= 8
            issues.append(
                QualityIssue(
                    code="prompt_too_short",
                    severity="major",
                    message="Enonce trop court pour une evaluation fiable.",
                    item_id=item.id,
                    item_index=index,
                )
            )

        if not has_source_reference:
            score -= 3
            issues.append(
                QualityIssue(
                    code="missing_source_reference",
                    severity="minor",
                    message="Reference source absente (section:...).",
                    item_id=item.id,
                    item_index=index,
                )
            )

        if (
            item.item_type
            in {ItemType.MCQ.value, ItemType.CLOZE.value, ItemType.OPEN_QUESTION.value}
            and not correct
        ):
            score -= 10
            issues.append(
                QualityIssue(
                    code="missing_expected_answer",
                    severity="critical",
                    message="Reponse attendue manquante.",
                    item_id=item.id,
                    item_index=index,
                )
            )

        if item.item_type == ItemType.MCQ.value:
            if len(distractors) < 3:
                score -= 8
                issues.append(
                    QualityIssue(
                        code="insufficient_distractors",
                        severity="major",
                        message="Un QCM doit contenir au moins 3 distracteurs.",
                        item_id=item.id,
                        item_index=index,
                    )
                )
            all_answers = [correct] + distractors if correct else distractors
            normalized = [entry.lower() for entry in all_answers if entry]
            if len(normalized) != len(set(normalized)):
                score -= 4
                issues.append(
                    QualityIssue(
                        code="duplicate_answers",
                        severity="minor",
                        message="Des reponses sont dupliquees (bonne reponse/distracteurs).",
                        item_id=item.id,
                        item_index=index,
                    )
                )

        if item.item_type == ItemType.CLOZE.value:
            hole_count = _count_cloze_holes(prompt)
            expected_count = len(_split_expected_answers_keep_duplicates(correct))
            if hole_count > 0 and expected_count < hole_count:
                score -= 10
                issues.append(
                    QualityIssue(
                        code="cloze_missing_answers",
                        severity="critical",
                        message=f"Texte a trous incomplet: {hole_count} trou(s) detecte(s) mais {expected_count} reponse(s).",
                        item_id=item.id,
                        item_index=index,
                    )
                )

        if item.item_type == ItemType.POLL.value:
            option_count = len({value.lower() for value in [*answer_options, *distractors]})
            if option_count < 2:
                score -= 8
                issues.append(
                    QualityIssue(
                        code="insufficient_poll_options",
                        severity="major",
                        message="Choix multiple incomplet: au moins 2 options sont requises.",
                        item_id=item.id,
                        item_index=index,
                    )
                )

        if item.item_type == ItemType.MATCHING.value:
            pair_count = len([fragment for fragment in re.split(r";|\n", correct) if "->" in fragment])
            if pair_count < 2:
                score -= 10
                issues.append(
                    QualityIssue(
                        code="insufficient_matching_pairs",
                        severity="critical",
                        message="Association incomplete: au moins 2 paires 'gauche -> droite' sont requises.",
                        item_id=item.id,
                        item_index=index,
                    )
                )

    score = max(0, min(100, score))
    readiness = "ready"
    if any(issue.severity == "critical" for issue in issues):
        readiness = "blocked"
    elif any(issue.severity == "major" for issue in issues):
        readiness = "review_needed"

    metrics = {
        "items_total": len(items),
        "item_types": dict(by_type),
        "difficulty_distribution": dict(by_difficulty),
        "critical_issues": sum(1 for issue in issues if issue.severity == "critical"),
        "major_issues": sum(1 for issue in issues if issue.severity == "major"),
        "minor_issues": sum(1 for issue in issues if issue.severity == "minor"),
    }
    return QualityPreviewResponse(
        project_id=project_id,
        content_set_id=content_set_id,
        overall_score=score,
        readiness=readiness,
        metrics=metrics,
        issues=issues,
    )


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _find_children(element: ET.Element, tag: str) -> list[ET.Element]:
    return [child for child in list(element) if _local_tag(child.tag) == tag]


def _find_first_child(element: ET.Element, tag: str) -> ET.Element | None:
    for child in list(element):
        if _local_tag(child.tag) == tag:
            return child
    return None


def _node_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _question_text(question: ET.Element) -> str:
    node = _find_first_child(question, "questiontext")
    if node is None:
        return ""
    text_node = _find_first_child(node, "text")
    return _node_text(text_node)


def _parse_pronote_xml(xml_content: str) -> tuple[list[dict[str, object]], Counter[str]]:
    try:
        root = ET.fromstring(xml_content.encode("utf-8"))
    except ET.ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"XML Pronote invalide: {exc}"
        ) from exc

    if _local_tag(root.tag) != "quiz":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le XML Pronote doit avoir une racine <quiz>",
        )

    parsed: list[dict[str, object]] = []
    by_type: Counter[str] = Counter()
    for question in root.findall(".//*"):
        if _local_tag(question.tag) != "question":
            continue
        qtype = (question.attrib.get("type") or "").strip().lower()
        if not qtype or qtype == "category":
            continue
        prompt = _question_text(question)
        if not prompt:
            continue

        if qtype == "multichoice":
            answers = _find_children(question, "answer")
            correct: list[str] = []
            incorrect: list[str] = []
            for answer in answers:
                fraction = (answer.attrib.get("fraction") or "0").strip()
                answer_text = _node_text(_find_first_child(answer, "text"))
                if not answer_text:
                    continue
                if fraction in {"100", "100.0"}:
                    correct.append(answer_text)
                else:
                    incorrect.append(answer_text)

            if len(correct) > 1:
                parsed.append(
                    {
                        "item_type": ItemType.POLL.value,
                        "prompt": prompt,
                        "correct_answer": None,
                        "distractors": [],
                        "answer_options": correct + incorrect,
                        "tags": ["import_pronote", "multiple_choice"],
                        "difficulty": "medium",
                        "feedback": "Import Pronote multichoix",
                    }
                )
                by_type[ItemType.POLL.value] += 1
            else:
                parsed.append(
                    {
                        "item_type": ItemType.MCQ.value,
                        "prompt": prompt,
                        "correct_answer": correct[0] if correct else "",
                        "distractors": incorrect,
                        "answer_options": [],
                        "tags": ["import_pronote", "single_choice"],
                        "difficulty": "medium",
                        "feedback": "Import Pronote multichoice",
                    }
                )
                by_type[ItemType.MCQ.value] += 1
            continue

        if qtype == "matching":
            pairs: list[str] = []
            for sub in _find_children(question, "subquestion"):
                left = _node_text(_find_first_child(sub, "text"))
                answer_node = _find_first_child(sub, "answer")
                right = (
                    _node_text(_find_first_child(answer_node, "text"))
                    if answer_node is not None
                    else ""
                )
                if left and right:
                    pairs.append(f"{left} -> {right}")
            parsed.append(
                {
                    "item_type": ItemType.MATCHING.value,
                    "prompt": prompt,
                    "correct_answer": "\n".join(pairs),
                    "distractors": [],
                    "answer_options": pairs,
                    "tags": ["import_pronote", "matching"],
                    "difficulty": "medium",
                    "feedback": "Import Pronote association",
                }
            )
            by_type[ItemType.MATCHING.value] += 1
            continue

        if qtype == "cloze":
            normalized_prompt, expected_answers, distractor_pool = _extract_cloze_answers_from_prompt(prompt)
            parsed.append(
                {
                    "item_type": ItemType.CLOZE.value,
                    "prompt": normalized_prompt or prompt,
                    "correct_answer": " || ".join(expected_answers),
                    "distractors": distractor_pool[:8],
                    "answer_options": [],
                    "tags": ["import_pronote", "cloze"],
                    "difficulty": "medium",
                    "feedback": "Import Pronote texte a trous",
                }
            )
            by_type[ItemType.CLOZE.value] += 1
            continue

        if qtype in {"shortanswer", "numerical"}:
            answers = _find_children(question, "answer")
            accepted = [_node_text(_find_first_child(answer, "text")) for answer in answers]
            accepted = [value for value in accepted if value]
            parsed.append(
                {
                    "item_type": ItemType.OPEN_QUESTION.value,
                    "prompt": prompt,
                    "correct_answer": " || ".join(accepted),
                    "distractors": [],
                    "answer_options": [],
                    "tags": ["import_pronote", qtype],
                    "difficulty": "medium",
                    "feedback": "Import Pronote reponse saisie",
                }
            )
            by_type[ItemType.OPEN_QUESTION.value] += 1

    return parsed, by_type


def _validate_document_payload(payload: SourceInitRequest) -> None:
    if not payload.filename or not payload.mime_type or payload.size_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filename, mime_type and size_bytes are required for document source",
        )
    if payload.size_bytes > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {settings.max_upload_bytes} bytes",
        )
    if payload.mime_type not in ALLOWED_DOCUMENT_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported MIME type"
        )


def _validate_non_document_payload(payload: SourceInitRequest) -> None:
    if (
        payload.source_type in {SourceType.LINK, SourceType.YOUTUBE}
        and not (payload.link_url or "").strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="link_url is required for youtube/link sources",
        )
    if payload.source_type == SourceType.TEXT and not (payload.raw_text or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="raw_text is required for text source",
        )
    if payload.source_type == SourceType.THEME and not (
        (payload.topic or payload.raw_text or "").strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="topic (or raw_text) is required for theme source",
        )


def _build_sections_for_text(text: str) -> list[dict[str, str]]:
    paragraphs = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    sections: list[dict[str, str]] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        sections.append(
            {
                "id": f"section:{index}",
                "title": f"Section {index}",
                "text": paragraph,
            }
        )
    return sections


def _get_user_project(db: Session, project_id: str, user_id: str) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _post_internal(url: str, payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        logger.exception("Internal service returned error", extra={"url": url})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc.response.text)
        ) from exc
    except httpx.HTTPError as exc:
        logger.exception("Internal service request failed", extra={"url": url})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
