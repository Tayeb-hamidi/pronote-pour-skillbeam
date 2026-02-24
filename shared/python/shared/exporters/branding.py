"""Shared branding and choice helpers for exporters."""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_EXPORT_TITLE = "SkillBeam - Questionnaire"


def bool_option(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "oui", "on"}
    return default


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_key(value: str) -> str:
    return normalize_text(value).lower()


def split_expected_answers(value: str | None) -> list[str]:
    if not value:
        return []
    chunks = re.split(r"\s*(?:\|\||;;|;|\n)\s*", value)
    seen: set[str] = set()
    answers: list[str] = []
    for chunk in chunks:
        candidate = normalize_text(chunk)
        if not candidate:
            continue
        key = normalize_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        answers.append(candidate)
    return answers


def dedupe_choices(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        candidate = normalize_text(value)
        if not candidate:
            continue
        key = normalize_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def collect_choice_rows(
    *,
    correct_answer: str | None,
    distractors: list[str],
    answer_options: list[str],
) -> list[tuple[str, bool]]:
    expected = split_expected_answers(correct_answer)
    expected_keys = {normalize_key(value) for value in expected}
    choices = dedupe_choices([*expected, *answer_options, *distractors])
    rows: list[tuple[str, bool]] = []
    for choice in choices:
        rows.append((choice, normalize_key(choice) in expected_keys))
    return rows


def label_item_type(item_type: str) -> str:
    labels = {
        "mcq": "Choix unique",
        "poll": "Choix multiple",
        "open_question": "Reponse a saisir",
        "matching": "Association",
        "cloze": "Texte a trous",
        "flashcard": "Flashcard",
        "brainstorming": "Brainstorming",
        "course_structure": "Structure de cours",
    }
    return labels.get(item_type, item_type)


def resolve_skillbeam_logo(options: dict) -> Path | None:
    raw_option = options.get("skillbeam_logo_path")
    env_option = os.getenv("SKILLBEAM_LOGO_PATH")
    candidates = [raw_option, env_option, Path(__file__).resolve().parent / "assets" / "skillbeam-logo.png"]
    for candidate in candidates:
        if not candidate:
            continue
        candidate_path = Path(str(candidate)).expanduser()
        if candidate_path.exists() and candidate_path.is_file():
            return candidate_path
    return None
