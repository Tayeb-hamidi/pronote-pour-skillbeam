from pathlib import Path

from docx import Document

from shared.enums import ItemType
from shared.exporters.docx_exporter import DocxExporter
from shared.exporters.pdf_exporter import PdfExporter
from shared.schemas import ContentItemOut, ContentSetResponse


def _content_set() -> ContentSetResponse:
    return ContentSetResponse(
        content_set_id="cs-1",
        project_id="project-1",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="i1",
                item_type=ItemType.MCQ,
                prompt="Prompt",
                correct_answer="A",
                distractors=["B", "C", "D"],
                answer_options=[],
                tags=[],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            )
        ],
    )


def test_docx_export(tmp_path: Path) -> None:
    exporter = DocxExporter()
    artifact = exporter.export(_content_set(), options={}, output_dir=tmp_path)

    assert (
        artifact.mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert artifact.filename.endswith(".docx")
    assert Path(artifact.artifact_path).exists()

    doc = Document(artifact.artifact_path)
    payload = "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
    assert "SkillBeam - Questionnaire" in payload
    assert "Question 1 - Choix unique" in payload
    assert "[ ] A" in payload


def test_pdf_export(tmp_path: Path) -> None:
    exporter = PdfExporter()
    artifact = exporter.export(_content_set(), options={}, output_dir=tmp_path)

    assert artifact.mime == "application/pdf"
    assert artifact.filename.endswith(".pdf")
    assert Path(artifact.artifact_path).exists()
    payload = Path(artifact.artifact_path).read_bytes()
    assert b"SkillBeam - Questionnaire" in payload
    assert b"Question 1 - Choix unique" in payload
    assert b"[ ] A" in payload
