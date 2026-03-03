"""Moodle XML exporter plugin."""

from __future__ import annotations

from pathlib import Path
import re
from xml.sax.saxutils import escape

from shared.exporters.base import BaseExporter
from shared.schemas import ContentSetResponse, ExportArtifact


NUMERIC_PATTERN = re.compile(r"^\s*-?\d+(?:[.,]\d+)?\s*$")


def _cdata(value: str) -> str:
    safe = (value or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def _is_numeric_answer(value: str | None) -> bool:
    if value is None:
        return False
    return bool(NUMERIC_PATTERN.match(value))


def _normalize_numeric_value(value: str) -> str:
    return value.strip().replace(",", ".")


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _clean_values(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_text(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(normalized)
    return cleaned


def _statement_html(prompt: str, *, numeric_mode: bool) -> str:
    subtitle = (
        "Reponse attendue: chiffres uniquement."
        if numeric_mode
        else "Lisez l'enonce, puis repondez precisement."
    )
    return (
        "<div style=\"background:linear-gradient(135deg,#fff6cf 0%,#f3de9b 100%);"
        "border:2px solid #d9b864;border-radius:14px;padding:16px 18px;"
        "margin:0 0 10px 0;box-shadow:0 4px 12px rgba(162,116,10,0.18);\">"
        f"<div style=\"font-size:24px;line-height:1.45;font-weight:800;color:#3b2a00;\">{escape(prompt)}</div>"
        f"<div style=\"margin-top:8px;font-size:14px;font-weight:700;color:#7a5a17;\">{escape(subtitle)}</div>"
        "</div>"
    )


class MoodleXmlExporter(BaseExporter):
    format_name = "moodle_xml"

    def export(
        self, content_set: ContentSetResponse, options: dict, output_dir: Path
    ) -> ExportArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = options.get("filename", f"content_{content_set.project_id}_moodle.xml")
        file_path = output_dir / filename

        rows = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>"]
        category = options.get("category", "$course$/SkillBeam")
        rows.extend(
            [
                '<question type="category">',
                "  <category>",
                f"    <text>{escape(category)}</text>",
                "  </category>",
                "</question>",
            ]
        )

        exported_count = 0
        for item in content_set.items:
            item_type_val = item.item_type.value if hasattr(item.item_type, "value") else str(item.item_type)
            if item_type_val == "mcq":
                prompt = _normalize_text(item.prompt)
                correct = _normalize_text(item.correct_answer)
                distractors = _clean_values(item.distractors)
                if not prompt or not correct:
                    continue
                rows.append('<question type="multichoice">')
                rows.append(f"  <name><text>{escape(str(prompt or '')[0:80])}</text></name>")
                prompt_html = _statement_html(prompt, numeric_mode=False)
                rows.append(
                    f"  <questiontext format=\"html\"><text>{_cdata(prompt_html)}</text></questiontext>"
                )
                rows.append("  <single>true</single>")
                rows.append("  <shuffleanswers>true</shuffleanswers>")
                rows.append("  <answernumbering>abc</answernumbering>")
                rows.append(
                    f'  <answer fraction="100"><text>{escape(correct)}</text><feedback><text></text></feedback></answer>'
                )
                for distractor in distractors:
                    rows.append(
                        f'  <answer fraction="0"><text>{escape(distractor)}</text><feedback><text></text></feedback></answer>'
                    )
                rows.append("</question>")
                exported_count += 1
            elif item_type_val == "poll":
                prompt = _normalize_text(item.prompt)
                distractors = _clean_values(item.distractors)
                correct = _normalize_text(item.correct_answer)
                all_options = [correct] + distractors if correct else distractors
                if not prompt or not all_options:
                    continue
                rows.append('<question type="multichoice">')
                rows.append(f"  <name><text>{escape(str(prompt or '')[0:80])}</text></name>")
                prompt_html = _statement_html(prompt, numeric_mode=False)
                rows.append(
                    f"  <questiontext format=\"html\"><text>{_cdata(prompt_html)}</text></questiontext>"
                )
                rows.append("  <single>false</single>")
                rows.append("  <shuffleanswers>true</shuffleanswers>")
                rows.append("  <answernumbering>abc</answernumbering>")
                for option in all_options:
                    if not option:
                        continue
                    rows.append(
                        f'  <answer fraction="100"><text>{escape(option)}</text><feedback><text></text></feedback></answer>'
                    )
                rows.append("</question>")
                exported_count += 1
            elif item_type_val == "open_question":
                prompt = _normalize_text(item.prompt)
                raw_answer = _normalize_text(item.correct_answer)
                if not prompt or not raw_answer:
                    continue
                numeric_mode = _is_numeric_answer(raw_answer)
                question_type = "numerical" if numeric_mode else "shortanswer"
                rows.append(f'<question type="{question_type}">')
                rows.append(f"  <name><text>{escape(str(prompt or '')[0:80])}</text></name>")
                prompt_html = _statement_html(prompt, numeric_mode=numeric_mode)
                rows.append(
                    f"  <questiontext format=\"html\"><text>{_cdata(prompt_html)}</text></questiontext>"
                )
                if numeric_mode:
                    rows.append("  <answer fraction=\"100\">")
                    rows.append(f"    <text>{escape(_normalize_numeric_value(raw_answer))}</text>")
                    rows.append("    <tolerance>0</tolerance>")
                    rows.append("    <feedback><text></text></feedback>")
                    rows.append("  </answer>")
                else:
                    rows.append(
                        f'  <answer fraction="100"><text>{escape(raw_answer)}</text><feedback><text></text></feedback></answer>'
                    )
                rows.append("</question>")
                exported_count += 1
            elif item_type_val == "course_structure":
                prompt = _normalize_text(item.prompt)
                if not prompt:
                    continue
                rows.append('<question type="description">')
                rows.append(f"  <name><text>{escape(str(prompt or '')[0:80])}</text></name>")
                # Use general formatting to present the structure directly
                html = (
                    "<div style=\"background-color:#f8f9fa;border-left:4px solid #4a6fa5;padding:16px;\">"
                    f"<div style=\"white-space:pre-wrap;font-family:inherit;\">{escape(prompt)}</div>"
                    "</div>"
                )
                rows.append(
                    f"  <questiontext format=\"html\"><text>{_cdata(html)}</text></questiontext>"
                )
                rows.append("</question>")
                exported_count += 1
            elif item_type_val in ("brainstorming", "flashcard"):
                prompt = _normalize_text(item.prompt)
                correct = _normalize_text(item.correct_answer)
                if not prompt:
                    continue
                rows.append('<question type="essay">')
                rows.append(f"  <name><text>{escape(str(prompt or '')[0:80])}</text></name>")
                prompt_html = _statement_html(prompt, numeric_mode=False)
                rows.append(
                    f"  <questiontext format=\"html\"><text>{_cdata(prompt_html)}</text></questiontext>"
                )
                if correct:
                    feedback_html = f"<div style=\"padding:12px;background:#eef7e5;border-left:4px solid #7bc043;\"><strong>Éléments attendus :</strong><br/><br/><div style=\"white-space:pre-wrap;\">{escape(correct)}</div></div>"
                    rows.append(f"  <generalfeedback format=\"html\"><text>{_cdata(feedback_html)}</text></generalfeedback>")
                rows.append("  <responseformat>editor</responseformat>")
                rows.append("  <responserequired>1</responserequired>")
                rows.append("  <responsefieldlines>10</responsefieldlines>")
                rows.append("</question>")
                exported_count += 1
            elif item_type_val == "matching":
                prompt = _normalize_text(item.prompt)
                raw_correct = item.correct_answer or ""
                if not prompt or not raw_correct.strip():
                    continue
                rows.append('<question type="matching">')
                rows.append(f"  <name><text>{escape(str(prompt or '')[0:80])}</text></name>")
                prompt_html = _statement_html(prompt, numeric_mode=False)
                rows.append(
                    f"  <questiontext format=\"html\"><text>{_cdata(prompt_html)}</text></questiontext>"
                )
                rows.append("  <shuffleanswers>true</shuffleanswers>")
                
                # Parse "A -> B\nC -> D"
                pairs = []
                for line in raw_correct.split('\n'):
                    parts = line.split('->', 1)
                    if len(parts) == 2:
                        left = _normalize_text(parts[0])
                        right = _normalize_text(parts[1])
                        if left and right:
                            pairs.append((left, right))
                
                if pairs:
                    for left, right in pairs:
                        rows.append("  <subquestion format=\"html\">")
                        rows.append(f"    <text>{_cdata(left)}</text>")
                        rows.append(f"    <answer><text>{escape(right)}</text></answer>")
                        rows.append("  </subquestion>")
                    rows.append("</question>")
                    exported_count += 1
                else:
                    # fallback to essay if it fails to parse
                    rows.pop() # remove shuffleanswers
                    rows.pop() # remove questiontext
                    rows.pop() # remove name
                    rows.pop() # remove question
                    
            elif item_type_val == "cloze":
                prompt = _normalize_text(item.prompt)
                correct = _normalize_text(item.correct_answer)
                if not prompt:
                    continue
                # For Moodle XML, it's easier to just pass the cloze multianswer format if correctly written 
                # Otherwise, fallback to an essay where the user fills in the blanks manually
                # Let's try to adapt the MultiChoice elements to Moodle CLOZE syntax: {1:SHORTANSWER:=BonneReponse}
                cloze_text = prompt
                
                def repl_cloze(match):
                    opts = match.group(1).split('~')
                    if not opts:
                        return "____"
                    correct_opt = None
                    distractors = []
                    for o in opts:
                        if o.startswith('='):
                            correct_opt = o[1:]
                        else:
                            distractors.append(o)
                    
                    if not correct_opt and distractors:
                        correct_opt = distractors.pop(0)
                        
                    if correct_opt:
                        return f"{{1:SHORTANSWER:={escape(correct_opt)}}}"
                    return "____"
                
                cloze_text = re.sub(r"\{\:MULTICHOICE:(.*?)\}", repl_cloze, cloze_text)
                # also replace ____ with a generic shortanswer if correct is available
                if "____" in cloze_text and correct and "%100%" not in cloze_text and "SHORTANSWER" not in cloze_text:
                     cloze_text = cloze_text.replace("____", f"{{1:SHORTANSWER:={escape(correct)}}}")
                
                if "{1:SHORTANSWER" in cloze_text:
                    rows.append('<question type="cloze">')
                    rows.append(f"  <name><text>{escape(str(prompt or '')[0:80])}</text></name>")
                    # The text IS the question in Moodle Cloze
                    html = (
                        "<div style=\"background:linear-gradient(135deg,#fff6cf 0%,#f3de9b 100%);"
                        "border:2px solid #d9b864;border-radius:14px;padding:16px 18px;"
                        "margin:0 0 10px 0;box-shadow:0 4px 12px rgba(162,116,10,0.18);\">"
                        f"<div style=\"font-size:24px;line-height:1.45;font-weight:800;color:#3b2a00;\">{cloze_text}</div>"
                        "</div>"
                    )
                    rows.append(
                        f"  <questiontext format=\"html\"><text>{_cdata(html)}</text></questiontext>"
                    )
                    rows.append("</question>")
                    exported_count += 1
                else: # fallback essay
                    rows.append('<question type="essay">')
                    rows.append(f"  <name><text>{escape(str(prompt or '')[0:80])}</text></name>")
                    prompt_html = _statement_html(prompt, numeric_mode=False)
                    rows.append(
                        f"  <questiontext format=\"html\"><text>{_cdata(prompt_html)}</text></questiontext>"
                    )
                    if correct:
                        feedback_html = f"<div style=\"padding:12px;background:#eef7e5;border-left:4px solid #7bc043;\"><strong>Réponses attendues :</strong><br/><br/><div style=\"white-space:pre-wrap;\">{escape(correct)}</div></div>"
                        rows.append(f"  <generalfeedback format=\"html\"><text>{_cdata(feedback_html)}</text></generalfeedback>")
                    rows.append("  <responseformat>editor</responseformat>")
                    rows.append("  <responserequired>1</responserequired>")
                    rows.append("  <responsefieldlines>5</responsefieldlines>")
                    rows.append("</question>")
                    exported_count += 1
                    
        if exported_count == 0:
            raise ValueError("Aucune question exportable: types non reconnus ou réponses manquantes.")
        rows.append("</quiz>")

        file_path.write_text("\n".join(rows), encoding="utf-8")
        return ExportArtifact(
            artifact_path=str(file_path), mime="application/xml", filename=filename
        )
