"""Unit tests for Pronote import parsing and pedagogical quality preview."""

from __future__ import annotations

from app.main import _compute_quality_preview, _parse_pronote_xml
from shared.models import Item


def test_parse_pronote_xml_extracts_supported_items() -> None:
    xml_payload = """<?xml version="1.0" encoding="UTF-8" ?>
<quiz>
  <question type="category"><category><text><![CDATA[x]]></text></category></question>
  <question type="multichoice">
    <questiontext format="plain_text"><text><![CDATA[Question A]]></text></questiontext>
    <answer fraction="100" format="plain_text"><text><![CDATA[Bonne]]></text></answer>
    <answer fraction="0" format="plain_text"><text><![CDATA[Fausse 1]]></text></answer>
    <answer fraction="0" format="plain_text"><text><![CDATA[Fausse 2]]></text></answer>
  </question>
  <question type="matching">
    <questiontext format="html"><text><![CDATA[Associer]]></text></questiontext>
    <subquestion><text><![CDATA[A]]></text><answer><text><![CDATA[a]]></text></answer></subquestion>
    <subquestion><text><![CDATA[B]]></text><answer><text><![CDATA[b]]></text></answer></subquestion>
  </question>
</quiz>
"""

    items, breakdown = _parse_pronote_xml(xml_payload)
    assert len(items) == 2
    assert breakdown["mcq"] == 1
    assert breakdown["matching"] == 1


def test_quality_preview_flags_critical_issues() -> None:
    item = Item(
        content_set_id="cs1",
        item_type="mcq",
        prompt="Q ?",
        correct_answer="",
        distractors_json=["A"],
        answer_options_json=[],
        tags_json=[],
        difficulty="hard",
        feedback="",
        source_reference=None,
        position=0,
    )

    preview = _compute_quality_preview(project_id="p1", content_set_id="cs1", items=[item])
    assert preview.readiness in {"blocked", "review_needed"}
    assert preview.overall_score < 100
    assert any(issue.code == "missing_expected_answer" for issue in preview.issues)
