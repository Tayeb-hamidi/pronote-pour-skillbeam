from pathlib import Path
import xml.etree.ElementTree as ET

from shared.enums import ItemType
from shared.exporters.pronote_xml_exporter import PronoteXmlExporter
from shared.schemas import ContentItemOut, ContentSetResponse


def _sample_content_set() -> ContentSetResponse:
    return ContentSetResponse(
        content_set_id="cs-1",
        project_id="project-1",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-1",
                item_type=ItemType.MCQ,
                prompt="Quelle est la capitale de la France ?",
                correct_answer="Paris",
                distractors=["Lyon", "Marseille", "Toulouse"],
                answer_options=[],
                tags=["geo"],
                difficulty="easy",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
            ContentItemOut(
                id="item-2",
                item_type=ItemType.MCQ,
                prompt="2 + 2 = ?",
                correct_answer="4",
                distractors=["3", "5", "22"],
                answer_options=[],
                tags=["math"],
                difficulty="easy",
                feedback="",
                source_reference="section:2",
                position=1,
            ),
        ],
    )


def _sample_content_set_with_extended_types() -> ContentSetResponse:
    return ContentSetResponse(
        content_set_id="cs-2",
        project_id="project-2",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-1",
                item_type=ItemType.CLOZE,
                prompt="Le transfert thermique par contact se nomme ____.",
                correct_answer="conduction",
                distractors=["convection", "rayonnement", "evaporation"],
                answer_options=[],
                tags=["cloze"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
            ContentItemOut(
                id="item-2",
                item_type=ItemType.MATCHING,
                prompt="Associez chaque notion a sa definition.",
                correct_answer="Conduction -> transfert par contact ; Convection -> transfert par deplacement d'un fluide",
                distractors=[],
                answer_options=["Rayonnement -> transfert par onde electromagnetique"],
                tags=["matching"],
                difficulty="medium",
                feedback="",
                source_reference="section:2",
                position=1,
            ),
        ],
    )


def test_pronote_xml_structure_and_order(tmp_path: Path) -> None:
    exporter = PronoteXmlExporter()
    artifact = exporter.export(
        _sample_content_set(),
        options={"name": "SkillBeam", "answernumbering": "123", "niveau": "", "matiere": ""},
        output_dir=tmp_path,
    )

    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")

    assert xml_content.startswith('<?xml version="1.0" encoding="UTF-8" ?>')
    assert "<quiz>" in xml_content and "</quiz>" in xml_content

    # 1st question must be category + CDATA infos.
    assert '<question type="category">' in xml_content
    first_q_index = xml_content.index('<question type="category">')
    first_mcq_index = xml_content.index('<question type="multichoice">')
    assert first_q_index < first_mcq_index
    assert "<![CDATA[" in xml_content
    assert "<infos>" in xml_content
    assert "<name>SkillBeam</name>" in xml_content

    # Verify strict order of multichoice sub-tags.
    mcq_start = xml_content.index('<question type="multichoice">')
    mcq_end = xml_content.index("</question>", mcq_start)
    mcq_block = xml_content[mcq_start:mcq_end]

    expected_order = [
        "<name><text><![CDATA[]]></text></name>",
        '<questiontext format="plain_text">',
        "<externallink/>",
        "<usecase>1</usecase>",
        "<defaultgrade>1</defaultgrade>",
        "<editeur>0</editeur>",
        "<single>true</single>",
        "<shuffleanswers>truez</shuffleanswers>",
        '<answer fraction="100" format="plain_text">',
    ]

    positions = [mcq_block.index(fragment) for fragment in expected_order]
    assert positions == sorted(positions)

    # XML must be well-formed.
    ET.fromstring(xml_content)


def test_pronote_xml_supports_cloze_and_matching(tmp_path: Path) -> None:
    exporter = PronoteXmlExporter()
    artifact = exporter.export(
        _sample_content_set_with_extended_types(),
        options={
            "name": "ESS6_V2",
            "answernumbering": "123",
            "niveau": "1ERE",
            "matiere": "INGENIER.&DEV.DURAB.",
        },
        output_dir=tmp_path,
    )

    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")

    assert '<question type="cloze" desc="variable">' in xml_content
    assert (
        "{:MULTICHOICE:%100%conduction#~%0%convection#~%0%rayonnement#~%0%evaporation}"
        in xml_content
    )
    cloze_start = xml_content.index('<question type="cloze" desc="variable">')
    cloze_end = xml_content.index("</question>", cloze_start)
    cloze_block = xml_content[cloze_start:cloze_end]
    cloze_expected_order = [
        "<name><text><![CDATA[",
        '<questiontext format="html">',
        "<externallink/>",
        "<usecase>1</usecase>",
        "<defaultgrade>1</defaultgrade>",
        "<editeur>0</editeur>",
    ]
    cloze_positions = [cloze_block.index(fragment) for fragment in cloze_expected_order]
    assert cloze_positions == sorted(cloze_positions)

    assert '<question type="matching">' in xml_content
    assert "<subquestion>" in xml_content
    assert "<text><![CDATA[Conduction]]></text>" in xml_content
    assert "<text><![CDATA[transfert par contact]]></text>" in xml_content
    assert "<shuffleanswers>true</shuffleanswers>" in xml_content
    matching_start = xml_content.index('<question type="matching">')
    matching_end = xml_content.index("</question>", matching_start)
    matching_block = xml_content[matching_start:matching_end]
    matching_expected_order = [
        "<name><text><![CDATA[",
        '<questiontext format="html">',
        "<externallink/>",
        "<usecase>1</usecase>",
        "<defaultgrade>1</defaultgrade>",
        "<editeur>0</editeur>",
        "<subquestion>",
        "<shuffleanswers>true</shuffleanswers>",
    ]
    matching_positions = [matching_block.index(fragment) for fragment in matching_expected_order]
    assert matching_positions == sorted(matching_positions)

    ET.fromstring(xml_content)


def test_pronote_xml_skips_items_without_expected_answer(tmp_path: Path) -> None:
    exporter = PronoteXmlExporter()
    content_set = ContentSetResponse(
        content_set_id="cs-3",
        project_id="project-3",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-valid",
                item_type=ItemType.MCQ,
                prompt="Question valide",
                correct_answer="Bonne",
                distractors=["Mauvaise A", "Mauvaise B"],
                answer_options=[],
                tags=["pronote"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
            ContentItemOut(
                id="item-missing-answer",
                item_type=ItemType.MCQ,
                prompt="Question sans reponse",
                correct_answer="",
                distractors=["X", "Y"],
                answer_options=[],
                tags=["pronote"],
                difficulty="medium",
                feedback="",
                source_reference="section:2",
                position=1,
            ),
            ContentItemOut(
                id="item-multi-missing-answer",
                item_type=ItemType.POLL,
                prompt="Question multiple sans bonne reponse",
                correct_answer="",
                distractors=[],
                answer_options=["Option 1", "Option 2"],
                tags=["pronote", "multiple_choice"],
                difficulty="medium",
                feedback="",
                source_reference="section:3",
                position=2,
            ),
        ],
    )

    artifact = exporter.export(content_set, options={}, output_dir=tmp_path)
    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")

    assert "Question valide" in xml_content
    assert "Question sans reponse" not in xml_content
    assert "Question multiple sans bonne reponse" not in xml_content
    ET.fromstring(xml_content)


def test_pronote_xml_exports_multiple_choice_with_multiple_expected_answers(
    tmp_path: Path,
) -> None:
    exporter = PronoteXmlExporter()
    content_set = ContentSetResponse(
        content_set_id="cs-4",
        project_id="project-4",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-poll",
                item_type=ItemType.POLL,
                prompt="Quels artistes sont impressionnistes ?",
                correct_answer="Monet || Renoir",
                distractors=[],
                answer_options=["Monet", "Renoir", "Picasso", "Dali"],
                tags=["pronote", "multiple_choice"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
        ],
    )

    artifact = exporter.export(content_set, options={}, output_dir=tmp_path)
    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")

    assert "<single>false</single>" in xml_content
    assert "<text><![CDATA[Monet]]></text>" in xml_content
    assert "<text><![CDATA[Renoir]]></text>" in xml_content
    assert "<text><![CDATA[Picasso]]></text>" in xml_content
    ET.fromstring(xml_content)


def test_pronote_xml_matching_filters_fragment_pairs(tmp_path: Path) -> None:
    exporter = PronoteXmlExporter()
    content_set = ContentSetResponse(
        content_set_id="cs-5",
        project_id="project-5",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-matching",
                item_type=ItemType.MATCHING,
                prompt="Associez chaque notion du reseau a sa definition.",
                correct_answer=(
                    "On suppose le reseau parfait -> est-a-dire sans perte de lettres ; "
                    "Le diagramme temporel -> represente l'ordre des transmissions ; "
                    "Le reseau parfait -> garantit une transmission sans perte."
                ),
                distractors=[],
                answer_options=[
                    "Toutes les lettres -> sont surement arrivees dans l'ordre ; "
                    "Les lettres -> arrivent au destinataire ; "
                    "Bien entendu -> ajout de protocole"
                ],
                tags=["matching"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
            ContentItemOut(
                id="item-mcq",
                item_type=ItemType.MCQ,
                prompt="Question de securite",
                correct_answer="Bonne",
                distractors=["Mauvaise A", "Mauvaise B", "Mauvaise C"],
                answer_options=[],
                tags=[],
                difficulty="easy",
                feedback="",
                source_reference="section:2",
                position=1,
            ),
        ],
    )

    artifact = exporter.export(content_set, options={}, output_dir=tmp_path)
    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")

    assert "<text><![CDATA[Le diagramme temporel]]></text>" in xml_content
    assert "<text><![CDATA[Le reseau parfait]]></text>" in xml_content
    assert "On suppose le reseau parfait" not in xml_content
    assert "Toutes les lettres" not in xml_content
    assert "Les lettres" not in xml_content
    assert "Bien entendu" not in xml_content
    assert "est le suivant" not in xml_content
    root = ET.fromstring(xml_content)
    matching = next(question for question in root.findall("question") if question.get("type") == "matching")
    for subquestion in matching.findall("subquestion"):
        label = (subquestion.findtext("text") or "").strip()
        assert len(label.split()) >= 2


def test_pronote_xml_matching_handles_accented_cest_a_dire_definitions(tmp_path: Path) -> None:
    exporter = PronoteXmlExporter()
    content_set = ContentSetResponse(
        content_set_id="cs-7",
        project_id="project-7",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-matching-accent",
                item_type=ItemType.MATCHING,
                prompt="Associez chaque notion reseau a sa definition.",
                correct_answer=(
                    "Le reseau parfait -> c'est-à-dire sans perte de lettres et avec une latence stable ; "
                    "Le protocole de repetition -> permet de relancer une trame manquante apres temporisation."
                ),
                distractors=[],
                answer_options=[
                    "Le diagramme temporel -> represente la chronologie complete des transmissions."
                ],
                tags=["matching"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
        ],
    )

    artifact = exporter.export(content_set, options={}, output_dir=tmp_path)
    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")

    assert "est-à-dire" not in xml_content
    assert "est le suivant" not in xml_content
    assert "<text><![CDATA[Le reseau parfait]]></text>" in xml_content
    assert "<text><![CDATA[sans perte de lettres et avec une latence stable]]></text>" in xml_content
    ET.fromstring(xml_content)


def test_pronote_xml_matching_can_export_items_tagged_association_even_if_type_is_open_question(
    tmp_path: Path,
) -> None:
    exporter = PronoteXmlExporter()
    content_set = ContentSetResponse(
        content_set_id="cs-6",
        project_id="project-6",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-open-association",
                item_type=ItemType.OPEN_QUESTION,
                prompt="Associez chaque notion du protocole a sa definition.",
                correct_answer=(
                    "Le diagramme temporel -> represente l'ordre chronologique des transmissions ; "
                    "Le protocole de repetition -> renvoie une trame en cas d'absence d'accuse de reception ; "
                    "Le reseau parfait -> garantit une transmission sans perte."
                ),
                distractors=[],
                answer_options=[],
                tags=["association_pairs", "pronote"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
        ],
    )

    artifact = exporter.export(content_set, options={}, output_dir=tmp_path)
    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")
    root = ET.fromstring(xml_content)

    matching_questions = [question for question in root.findall("question") if question.get("type") == "matching"]
    assert len(matching_questions) == 1
    subquestions = matching_questions[0].findall("subquestion")
    assert len(subquestions) >= 2


def test_pronote_xml_matching_prioritizes_clean_correct_answer_pairs_over_noisy_options(
    tmp_path: Path,
) -> None:
    exporter = PronoteXmlExporter()
    content_set = ContentSetResponse(
        content_set_id="cs-8",
        project_id="project-8",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-matching-priority",
                item_type=ItemType.MATCHING,
                prompt="Associez chaque notion reseau a sa definition.",
                correct_answer=(
                    "Le diagramme temporel -> represente la chronologie d'envoi et de reception des trames ; "
                    "Le protocole de repetition -> relance une trame quand l'accuse de reception n'arrive pas"
                ),
                distractors=[],
                answer_options=[
                    "On suppose le reseau parfait, c -> est-a-dire sans perte ; "
                    "Toutes les lettres -> sont probablement arrivees ; "
                    "Bien entendu -> ajout de protocole"
                ],
                tags=["matching", "association_pairs", "pronote"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
        ],
    )

    artifact = exporter.export(content_set, options={}, output_dir=tmp_path)
    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")
    root = ET.fromstring(xml_content)

    matching = next(question for question in root.findall("question") if question.get("type") == "matching")
    labels = [(sub.findtext("text") or "").strip() for sub in matching.findall("subquestion")]
    assert labels
    assert "Le diagramme temporel" in labels
    assert "Le protocole de repetition" in labels
    assert all("On suppose" not in label for label in labels)
    assert all("Toutes les lettres" not in label for label in labels)


def test_pronote_xml_matching_filters_generic_labels_like_exemple_and_quelques(tmp_path: Path) -> None:
    exporter = PronoteXmlExporter()
    content_set = ContentSetResponse(
        content_set_id="cs-9",
        project_id="project-9",
        status="generated",
        language="fr",
        level="intermediate",
        items=[
            ContentItemOut(
                id="item-matching-generic",
                item_type=ItemType.MATCHING,
                prompt="Associez chaque notion a sa definition.",
                correct_answer=(
                    "Exemple -> Une adresse IPv4 comporte un identifiant reseau et un identifiant hote ; "
                    "Quelques contraintes -> Un reseau doit rester disponible pour les utilisateurs ; "
                    "Le protocole de repetition -> relance une trame en absence d'accuse de reception."
                ),
                distractors=[],
                answer_options=[
                    "Adresse IPv4 -> identifie un reseau et un equipement pour router les paquets."
                ],
                tags=["matching", "association_pairs", "pronote"],
                difficulty="medium",
                feedback="",
                source_reference="section:1",
                position=0,
            ),
        ],
    )

    artifact = exporter.export(content_set, options={}, output_dir=tmp_path)
    xml_content = Path(artifact.artifact_path).read_text(encoding="utf-8")
    root = ET.fromstring(xml_content)

    matching = next(question for question in root.findall("question") if question.get("type") == "matching")
    labels = [(sub.findtext("text") or "").strip() for sub in matching.findall("subquestion")]
    assert labels
    assert all(label.lower() not in {"exemple", "quelques contraintes"} for label in labels)
    assert "Le protocole de repetition" in labels or "Adresse IPv4" in labels
