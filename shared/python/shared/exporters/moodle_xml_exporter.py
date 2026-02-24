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
            if item.item_type.value == "mcq":
                prompt = _normalize_text(item.prompt)
                correct = _normalize_text(item.correct_answer)
                distractors = _clean_values(item.distractors)
                if not prompt or not correct:
                    continue
                rows.append('<question type="multichoice">')
                rows.append(f"  <name><text>{escape(prompt[:80])}</text></name>")
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
            elif item.item_type.value == "open_question":
                prompt = _normalize_text(item.prompt)
                raw_answer = _normalize_text(item.correct_answer)
                if not prompt or not raw_answer:
                    continue
                numeric_mode = _is_numeric_answer(raw_answer)
                question_type = "numerical" if numeric_mode else "shortanswer"
                rows.append(f'<question type="{question_type}">')
                rows.append(f"  <name><text>{escape(prompt[:80])}</text></name>")
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
        if exported_count == 0:
            raise ValueError("Aucune question exportable: reponse attendue manquante.")
        rows.append("</quiz>")

        file_path.write_text("\n".join(rows), encoding="utf-8")
        return ExportArtifact(
            artifact_path=str(file_path), mime="application/xml", filename=filename
        )
