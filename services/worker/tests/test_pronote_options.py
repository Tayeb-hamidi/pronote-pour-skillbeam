from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app import tasks


def test_normalize_pronote_name_from_filename() -> None:
    assert tasks._normalize_pronote_name("revolution_francaise.pdf") == "revolution_francaise"


def test_select_pronote_category_name_skips_placeholders() -> None:
    name = tasks._select_pronote_category_name(
        ["SkillBeam", "Projet Wizard", "Revolution francaise", "Autre valeur"]
    )
    assert name == "Revolution francaise"


def test_prepare_export_options_derives_name_for_pronote_placeholder(monkeypatch) -> None:
    monkeypatch.setattr(
        tasks,
        "_derive_pronote_category_name",
        lambda **_: "Revolution francaise",
    )

    resolved = tasks._prepare_export_options(
        db=object(),  # type: ignore[arg-type]
        project_id="project-1",
        content_set=SimpleNamespace(source_document_id=None),  # type: ignore[arg-type]
        format_name="pronote_xml",
        options={"name": "SkillBeam", "answernumbering": "123"},
    )

    assert resolved["name"] == "Revolution francaise"
    assert resolved["answernumbering"] == "123"


def test_prepare_export_options_keeps_custom_pronote_name() -> None:
    resolved = tasks._prepare_export_options(
        db=object(),  # type: ignore[arg-type]
        project_id="project-1",
        content_set=SimpleNamespace(source_document_id=None),  # type: ignore[arg-type]
        format_name="pronote_xml",
        options={"name": "Histoire 4e"},
    )

    assert resolved["name"] == "Histoire 4e"
