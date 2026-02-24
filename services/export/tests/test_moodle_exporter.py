from pathlib import Path
import xml.etree.ElementTree as ET

from shared.enums import ItemType
from shared.exporters.moodle_xml_exporter import MoodleXmlExporter
from shared.schemas import ContentItemOut, ContentSetResponse


def _content_set() -> ContentSetResponse:
    return ContentSetResponse(
        content_set_id="cs-moodle-1",
        project_id="project-1",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="i-num",
                item_type=ItemType.OPEN_QUESTION,
                prompt="Combien d'annees d'experience sont mentionnees ?",
                correct_answer="14",
                distractors=[],
                answer_options=[],
                tags=["numeric_value"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
            ContentItemOut(
                id="i-short",
                item_type=ItemType.OPEN_QUESTION,
                prompt="Nommez le dispositif pedagogique cite dans le texte.",
                correct_answer="SkillBeam AI-Edu",
                distractors=[],
                answer_options=[],
                tags=["free_response"],
                difficulty="medium",
                feedback="",
                source_reference="section:2",
                position=1,
            ),
        ],
    )


def test_moodle_export_applies_gold_statement_style_and_numeric_mode(tmp_path: Path) -> None:
    exporter = MoodleXmlExporter()
    artifact = exporter.export(_content_set(), options={}, output_dir=tmp_path)

    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")
    assert "linear-gradient(135deg,#fff6cf 0%,#f3de9b 100%)" in xml_content
    assert "font-size:24px" in xml_content
    assert '<question type="numerical">' in xml_content
    assert "<tolerance>0</tolerance>" in xml_content
    assert '<question type="shortanswer">' in xml_content

    root = ET.fromstring(xml_content)
    assert root.tag == "quiz"


def test_moodle_export_skips_items_without_expected_answer(tmp_path: Path) -> None:
    exporter = MoodleXmlExporter()
    content_set = ContentSetResponse(
        content_set_id="cs-moodle-2",
        project_id="project-2",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="i-valid",
                item_type=ItemType.OPEN_QUESTION,
                prompt="Donnez le nom du dispositif.",
                correct_answer="SkillBeam AI-Edu",
                distractors=[],
                answer_options=[],
                tags=[],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
            ContentItemOut(
                id="i-invalid",
                item_type=ItemType.OPEN_QUESTION,
                prompt="Question sans reponse attendue",
                correct_answer="",
                distractors=[],
                answer_options=[],
                tags=[],
                difficulty="medium",
                feedback="",
                source_reference="section:2",
                position=1,
            ),
        ],
    )

    artifact = exporter.export(content_set, options={}, output_dir=tmp_path)
    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")

    assert "Donnez le nom du dispositif." in xml_content
    assert "Question sans reponse attendue" not in xml_content
    ET.fromstring(xml_content)
