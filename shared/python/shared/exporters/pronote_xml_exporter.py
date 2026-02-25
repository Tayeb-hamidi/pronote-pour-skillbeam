"""Dedicated PRONOTE XML exporter plugin."""

from __future__ import annotations

from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET

from shared.exporters.base import BaseExporter
from shared.schemas import ContentSetResponse, ExportArtifact

CLOZE_PLACEHOLDER_PATTERN = re.compile(
    r"(_{3,}|\{\{blank\}\}|\[blank\]|\(blank\))", flags=re.IGNORECASE
)
CLOZE_TOKEN_PATTERN = re.compile(r"\{\:MULTICHOICE:(.*?)\}", flags=re.IGNORECASE | re.DOTALL)
CLOZE_OPTION_PATTERN = re.compile(r"%([^%]+)%([^#]+)")
CLOZE_OPTION_PLACEHOLDER_PATTERN = re.compile(r"^option\s+[a-z]$", flags=re.IGNORECASE)
CLOZE_WORD_PATTERN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9'-]{2,}")
CLOZE_STOPWORDS: set[str] = {
    "quelle",
    "quelles",
    "comment",
    "pourquoi",
    "dans",
    "avec",
    "sans",
    "pour",
    "entre",
    "vous",
    "nous",
    "elle",
    "elles",
    "ils",
    "les",
    "des",
    "une",
    "un",
    "est",
    "sont",
    "être",
    "etre",
}
MATCHING_PLACEHOLDER_PATTERN = re.compile(
    r"^(definition\s+de|def\s+de|desc\s+de|element\s+[a-z0-9]+|notion\s+[a-z0-9]+|terme\s+[a-z0-9]+)\b",
    flags=re.IGNORECASE,
)
MATCHING_STOPWORDS: set[str] = {
    "comment",
    "pourquoi",
    "quelle",
    "quelles",
    "quels",
    "quoi",
    "ou",
    "quand",
    "combien",
    "liste",
    "definition",
    "question",
    "reponse",
    "associez",
    "associer",
}
MATCHING_BAD_LEFT_PREFIX_PATTERN = re.compile(
    r"^\s*(on|il|elle|ils|elles|nous|vous|ce|cet|cette|cela|ceci|bien|toutes?|chaque)\b",
    flags=re.IGNORECASE,
)
MATCHING_LEFT_NOISY_PHRASE_PATTERN = re.compile(
    r"^\s*(?:on\s+suppose|bien\s+entendu|toutes?\s+les|les\s+donn[eé]es?|les\s+informations?)\b",
    flags=re.IGNORECASE,
)
MATCHING_LEFT_BAD_START_TOKENS: set[str] = {
    "disponible",
    "probablement",
    "surement",
    "sûrement",
    "suivant",
    "suivante",
    "suivants",
    "suivantes",
    "quelques",
    "plusieurs",
    "exemple",
    "exemples",
    "cas",
    "maintenant",
}
MATCHING_RIGHT_NOISY_START_PATTERN = re.compile(
    r"^\s*(?:est\s+le\s+suivant|c['’]?\s*est\s*[-–]?\s*[aà]\s*[-–]?\s*dire|est\s*[-–]?\s*[aà]\s*[-–]?\s*dire|sont\s+probablement|il\s+pourrait\s+falloir)\b",
    flags=re.IGNORECASE,
)
MATCHING_RIGHT_NOISY_TAIL_PATTERN = re.compile(
    r"^\s*(?:est\s+le\s+suivant|sont\s+probablement|sont\s+s[ûu]rement|il\s+pourrait\s+falloir)\b",
    flags=re.IGNORECASE,
)
MATCHING_RIGHT_BAD_END_PATTERN = re.compile(
    r"(?:\b(?:de|du|des|d['’]?|a|à|au|aux|pour|avec|sans|sur|sous|dans|en|par|vers|et|ou|que|qui|dont)\b|[:;,\-])\.?$",
    flags=re.IGNORECASE,
)
MATCHING_WEAK_CERTAINTY_PATTERN = re.compile(
    r"\b(probablement|s[ûu]rement)\b",
    flags=re.IGNORECASE,
)
MATCHING_LEFT_VERB_PATTERN = re.compile(
    r"\b(est|sont|sera|seront|doit|doivent|peut|peuvent|faut|suppose|considere|considerent|arrive|arrivent|perd|perdent|decrit|decrivent|décrit|décrivent|signifie|signifient|indique|indiquent|explique|expliquent|definit|definissent|définit|définissent|represente|representent|représente|représentent|caracterise|caracterisent|caractérise|caractérisent|envoie|envoient|renvoie|renvoient|limite|limitent|transmet|transmettent|recoit|reçoit|recoivent|reçoivent|declenche|déclenche|declenchent|déclenchent|active|activent)\b",
    flags=re.IGNORECASE,
)
MATCHING_DEFINITION_PREFIX_PATTERN = re.compile(
    r"^\s*(?:(?:c['’]?\s*est|est)\s*[-–]?\s*[aà]\s*[-–]?\s*dire)\b[:\s,-]*",
    flags=re.IGNORECASE,
)
MATCHING_PREDICATE_PREFIX_PATTERN = re.compile(
    r"^\s*(est|sont|decrit(?:e|ent)?|décrit(?:e|ent)?|signifie(?:nt)?|indique(?:nt)?|explique(?:nt)?|definit|définit|definissent|définissent|correspond(?:ent)?\s+a|permet(?:tent)?\s+de|sert(?:vent)?\s+a|consiste(?:nt)?\s+a|represente(?:nt)?|représente(?:nt)?|caracterise(?:nt)?|caractérise(?:nt)?|garantit|garantissent|envoie(?:nt)?|renvoie(?:nt)?|limite(?:nt)?|transmet(?:tent)?|recoi(?:t|vent)|reçoi(?:t|vent)|declenche(?:nt)?|déclenche(?:nt)?|active(?:nt)?)\b",
    flags=re.IGNORECASE,
)
MATCHING_COPULA_ARTICLE_PATTERN = re.compile(
    r"^\s*(?:est|sont)\s+(?:une?\s+|le\s+|la\s+|les\s+|l['']\s*|des\s+|du\s+|d['']\s*)?",
    flags=re.IGNORECASE,
)
MATCHING_LEFT_ARTICLE_PHRASE_PATTERN = re.compile(
    r"(?:^|\b)(?:toutes?\s+|tous\s+|chaque\s+|certaines?\s+|certains?\s+|ces\s+)?"
    r"((?:l['’]|le|la|les|un|une|des|du)\s+[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]+){0,4})",
    flags=re.IGNORECASE,
)
MATCHING_WEAK_DEFINITION_PATTERN = re.compile(
    r"^(?:est|sont)\s+(?:le|la|les)\s+suivan(?:t|te|ts|tes)\b",
    flags=re.IGNORECASE,
)
MATCHING_INTRO_NOISE_PATTERN = re.compile(
    r"^\s*(?:on\s+suppose(?:\s+que)?|on\s+considere(?:\s+que)?|"
    r"bien\s+entendu|ainsi|alors|dans\s+ce\s+cas|en\s+pratique)\b[,:-]?\s*",
    flags=re.IGNORECASE,
)
MATCHING_CEST_A_DIRE_PATTERN = re.compile(
    r"\bc['’]?\s*est\s*[-–]?\s*[aà]\s*[-–]?\s*dire\b",
    flags=re.IGNORECASE,
)
MATCHING_LABEL_BANNED_TOKENS: set[str] = {
    "est",
    "sont",
    "decrit",
    "decrivent",
    "décrit",
    "décrivent",
    "signifie",
    "signifient",
    "indique",
    "indiquent",
    "explique",
    "expliquent",
    "definit",
    "definissent",
    "définit",
    "définissent",
    "represente",
    "representent",
    "représente",
    "représentent",
    "caracterise",
    "caracterisent",
    "caractérise",
    "caractérisent",
    "garantit",
    "garantissent",
    "envoie",
    "envoient",
    "renvoie",
    "renvoient",
    "limite",
    "limitent",
    "transmet",
    "transmettent",
    "recoit",
    "reçoit",
    "recoivent",
    "reçoivent",
    "declenche",
    "déclenche",
    "declenchent",
    "déclenchent",
    "active",
    "activent",
}
MATCHING_LEADING_ARTICLE_PATTERN = re.compile(
    r"^(?:l['’]|d['’]|le|la|les|un|une|des|du|de|au|aux)\s*",
    flags=re.IGNORECASE,
)
MATCHING_GENERIC_TOKEN_STOPWORDS: set[str] = {
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "de",
    "d",
    "l",
    "au",
    "aux",
    "on",
    "bien",
    "entendu",
    "ainsi",
    "alors",
    "donc",
    "tout",
    "tous",
    "toute",
    "toutes",
    "chaque",
    "certain",
    "certaine",
    "certains",
    "certaines",
    "ce",
    "cet",
    "cette",
    "ces",
    "est",
    "sont",
    "sera",
    "seront",
    "peut",
    "peuvent",
    "doit",
    "doivent",
    "faut",
    "suppose",
    "considere",
    "considerent",
    "arrive",
    "arrivent",
    "perd",
    "perdent",
    "envoie",
    "envoient",
    "renvoie",
    "renvoient",
    "limite",
    "limitent",
    "transmet",
    "transmettent",
    "recoit",
    "reçoit",
    "recoivent",
    "reçoivent",
    "declenche",
    "déclenche",
    "declenchent",
    "déclenchent",
    "active",
    "activent",
    "avec",
    "sans",
    "dans",
    "pour",
    "par",
    "vers",
    "entre",
    "quelques",
    "plusieurs",
    "exemple",
    "exemples",
    "cas",
    "maintenant",
    "chose",
    "choses",
}
MATCHING_GENERIC_SINGLE_LABEL_TOKENS: set[str] = {
    "lettre",
    "lettres",
    "message",
    "messages",
    "donnee",
    "donnees",
    "donnée",
    "données",
    "information",
    "informations",
    "element",
    "elements",
    "élément",
    "éléments",
    "notion",
    "notions",
    "concept",
    "concepts",
}
MATCHING_LEFT_FORBIDDEN_TOKENS: set[str] = {
    "pas",
    "si",
    "meme",
    "même",
    "cela",
    "ceci",
    "ainsi",
    "alors",
    "debut",
    "début",
    "cote",
    "côté",
    "bout",
    "temps",
    "faut",
    "font",
    "fait",
    "faire",
    "vont",
    "va",
    "arrive",
    "arriver",
    "arrivent",
    "mettre",
    "met",
    "mettent",
    "quelques",
    "plusieurs",
    "exemple",
    "exemples",
    "cas",
    "maintenant",
}
MATCHING_RIGHT_MIN_WORDS = 3


def _cdata(value: str) -> str:
    safe = (value or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _split_expected_answers(value: str | None) -> list[str]:
    if not value:
        return []
    chunks = re.split(r"\s*(?:\|\||;;|;|\n)\s*", value)
    seen: set[str] = set()
    answers: list[str] = []
    for chunk in chunks:
        normalized = _normalize_text(chunk)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        answers.append(normalized)
    return answers


def _dedupe_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = _normalize_text(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _derive_name(prompt: str) -> str:
    cleaned = _normalize_text(_strip_html(prompt))
    return cleaned[:120] if cleaned else ""


def _normalize_matching_side(value: str, *, max_words: int, min_words: int = 1) -> str | None:
    cleaned = re.sub(r"\s+", " ", (value or "")).strip(" -:;,.")
    if not cleaned:
        return None
    cleaned = re.sub(r"^[\W_]+|[\W_]+$", "", cleaned).strip()
    if not cleaned:
        return None
    # Fix unclosed parentheses left by the trailing non-word strip above.
    open_count = cleaned.count("(")
    close_count = cleaned.count(")")
    if open_count > close_count:
        last_open = cleaned.rfind("(")
        cleaned = cleaned[:last_open].strip(" -:;,.")
    if not cleaned:
        return None
    words = cleaned.split()
    if len(words) < min_words or len(words) > max_words:
        return None
    return cleaned


def _normalize_matching_left_display(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "")).strip()
    if not cleaned:
        return cleaned
    if cleaned[0].isalpha() and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _is_generic_matching_left_label(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (value or "")).strip(" -:;,.")
    if not cleaned:
        return True
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]+", cleaned)
    if not tokens:
        return True

    normalized_tokens = [_normalize_identifier(token) for token in tokens]
    content_tokens = [
        token
        for token in normalized_tokens
        if token and token not in MATCHING_GENERIC_TOKEN_STOPWORDS
    ]
    if not content_tokens:
        return True

    if content_tokens[0] in MATCHING_LEFT_BAD_START_TOKENS:
        return True
    if any(token in MATCHING_LEFT_FORBIDDEN_TOKENS for token in content_tokens):
        return True

    if len(tokens) == 1:
        sole_norm = content_tokens[0]
        if sole_norm in MATCHING_GENERIC_SINGLE_LABEL_TOKENS:
            return True

    return False


def _normalize_matching_left_candidate(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "")).strip(" -:;,.")
    if not cleaned:
        return cleaned
    phrase_match = MATCHING_LEFT_ARTICLE_PHRASE_PATTERN.search(cleaned)
    if phrase_match:
        cleaned = phrase_match.group(1).strip()
    cleaned = re.sub(
        r"^\s*(?:toutes?\s+|tous\s+|chaque\s+|certaines?\s+|certains?\s+|ces\s+)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    # Split on French relative pronouns / punctuation — require word boundary
    # on BOTH sides to avoid matching inside words like "analogique", "numérique".
    cleaned = re.split(
        r"\s*(?:,|;|qu[‘’]|\bqui\b|\bque\b|\bdont\b)\s*",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    cleaned = re.sub(
        r"\s+(?:de|du|des|d[‘’]?|pour|avec|sans|dans|sur|en|par|vers|et|ou)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def _normalize_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


def _coerce_matching_definition(left: str, right_raw: str) -> str | None:
    raw_right = _normalize_matching_side(right_raw, max_words=34, min_words=MATCHING_RIGHT_MIN_WORDS)
    right = raw_right
    if not right:
        return None
    right = MATCHING_DEFINITION_PREFIX_PATTERN.sub("", right).strip(" -:;,.")
    right = re.sub(r"^\s*est\s+le\s+suivant\s*,?\s*", "", right, flags=re.IGNORECASE)
    if MATCHING_CEST_A_DIRE_PATTERN.search(right):
        _, suffix = MATCHING_CEST_A_DIRE_PATTERN.split(right, maxsplit=1)
        right = suffix.strip(" -:;,.")
    right = re.sub(r"\s*;\s*", ", ", right)
    if not right:
        return None
    left_cleaned = re.sub(r"\s+", " ", left).strip()
    left_core = _strip_matching_leading_articles(left_cleaned)
    if left_cleaned:
        right = re.sub(rf"^\s*{re.escape(left_cleaned)}\s*[,:-]?\s*", "", right, flags=re.IGNORECASE)
    if left_core and left_core.lower() != left_cleaned.lower():
        right = re.sub(rf"^\s*{re.escape(left_core)}\s*[,:-]?\s*", "", right, flags=re.IGNORECASE)
    if left_core:
        right = re.sub(
            rf"^\s*(?:l['’]|le|la|les|un|une|des|du)\s+{re.escape(left_core)}\s*[,:-]?\s*",
            "",
            right,
            flags=re.IGNORECASE,
        )
    right = MATCHING_INTRO_NOISE_PATTERN.sub("", right).strip(" -:;,.")
    right = re.sub(r"^\s*que\s+", "", right, flags=re.IGNORECASE)
    if MATCHING_CEST_A_DIRE_PATTERN.search(right):
        _, suffix = MATCHING_CEST_A_DIRE_PATTERN.split(right, maxsplit=1)
        right = suffix.strip(" -:;,.")
    if MATCHING_WEAK_DEFINITION_PATTERN.match(right):
        return None
    # Strip bare copulas "est/sont" + optional article to produce a self-contained
    # noun-phrase definition.  Keep meaningful predicate verbs and just capitalise.
    copula_match = MATCHING_COPULA_ARTICLE_PATTERN.match(right)
    if copula_match and MATCHING_PREDICATE_PREFIX_PATTERN.match(right):
        stripped = right[copula_match.end():]
        if stripped and len(stripped.split()) >= MATCHING_RIGHT_MIN_WORDS:
            right = stripped[0].upper() + stripped[1:]
        else:
            right = right[0].upper() + right[1:]
    elif MATCHING_PREDICATE_PREFIX_PATTERN.match(right):
        right = right[0].upper() + right[1:]
    right = _normalize_matching_side(right, max_words=34, min_words=MATCHING_RIGHT_MIN_WORDS)
    if right and MATCHING_RIGHT_NOISY_START_PATTERN.match(right):
        right = None
    if right and MATCHING_RIGHT_BAD_END_PATTERN.search(right):
        right = None
    if not right and raw_right and not MATCHING_RIGHT_NOISY_START_PATTERN.match(raw_right):
        # Keep full sentence when trimming removed useful context.
        right = raw_right
    if right and MATCHING_RIGHT_BAD_END_PATTERN.search(right):
        return None
    if right and MATCHING_WEAK_DEFINITION_PATTERN.match(right):
        return None
    return right


def _strip_matching_leading_articles(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    changed = True
    while changed:
        changed = False
        next_cleaned = MATCHING_LEADING_ARTICLE_PATTERN.sub("", cleaned).strip()
        if next_cleaned != cleaned:
            cleaned = next_cleaned
            changed = True
    return cleaned


def _is_valid_matching_pair(left: str, right: str) -> bool:
    left_cleaned = re.sub(r"\s+", " ", left).strip(" -:;,.")
    right_cleaned = re.sub(r"\s+", " ", right).strip(" -:;,.")
    if not left_cleaned or not right_cleaned:
        return False
    if any(symbol in left_cleaned for symbol in (",", ";", ":")):
        return False
    if _is_generic_matching_left_label(left_cleaned):
        return False
    if MATCHING_WEAK_CERTAINTY_PATTERN.search(left_cleaned):
        return False
    if MATCHING_WEAK_CERTAINTY_PATTERN.search(right_cleaned):
        return False

    left_core = _strip_matching_leading_articles(left_cleaned)
    if MATCHING_LEFT_NOISY_PHRASE_PATTERN.match(left_cleaned):
        return False
    if re.search(r"\b(?:qui|que|qu['’]|dont)\b", left_cleaned, flags=re.IGNORECASE):
        return False
    left_tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]+", left_core)
    if not left_tokens:
        return False
    first_token = _normalize_identifier(left_tokens[0])
    if first_token in MATCHING_LEFT_BAD_START_TOKENS:
        return False
    if len(left_tokens) < 2:
        lone = _normalize_identifier(left_tokens[0])
        if not (
            len(lone) >= 4
            and lone not in MATCHING_GENERIC_SINGLE_LABEL_TOKENS
            and lone not in MATCHING_STOPWORDS
        ):
            return False
    if any(len(token.strip("'’-")) <= 1 for token in left_tokens):
        return False
    content_tokens = [
        token
        for token in left_tokens
        if _normalize_identifier(token) not in MATCHING_GENERIC_TOKEN_STOPWORDS
    ]
    if len(content_tokens) < 2:
        if not (
            len(content_tokens) == 1
            and len(_normalize_identifier(content_tokens[0])) >= 4
            and _normalize_identifier(content_tokens[0]) not in MATCHING_GENERIC_SINGLE_LABEL_TOKENS
            and (
                MATCHING_LEADING_ARTICLE_PATTERN.match(left_cleaned)
                or len(left_tokens) == 1
            )
        ):
            return False
    if len(left_tokens) > 8:
        return False

    left_key = _normalize_identifier(left_cleaned)
    right_key = _normalize_identifier(right_cleaned)
    if not left_key or not right_key:
        return False
    if left_key in MATCHING_STOPWORDS:
        return False
    if MATCHING_BAD_LEFT_PREFIX_PATTERN.match(left_cleaned):
        return False
    if MATCHING_LEFT_VERB_PATTERN.search(left_cleaned):
        return False
    if left_key == right_key:
        return False
    if MATCHING_PLACEHOLDER_PATTERN.match(left_cleaned) or MATCHING_PLACEHOLDER_PATTERN.match(right_cleaned):
        return False
    if right_cleaned.lower().startswith(("definition de ", "def de ", "desc de ")):
        return False
    if MATCHING_WEAK_DEFINITION_PATTERN.match(right_cleaned):
        return False
    if MATCHING_RIGHT_NOISY_START_PATTERN.match(right_cleaned):
        return False
    if MATCHING_RIGHT_BAD_END_PATTERN.search(right_cleaned):
        return False
    if len(right_cleaned.split()) < MATCHING_RIGHT_MIN_WORDS:
        return False
    if right_key.startswith(left_key):
        # Accept complete predicate definitions after the concept label.
        right_tail = re.sub(rf"^\s*{re.escape(left_cleaned)}\s*", "", right_cleaned, flags=re.IGNORECASE).strip()
        if left_core and right_tail == right_cleaned:
            right_tail = re.sub(rf"^\s*{re.escape(left_core)}\s*", "", right_cleaned, flags=re.IGNORECASE).strip()
        if len(right_tail.split()) < 3:
            return False
        if MATCHING_RIGHT_NOISY_TAIL_PATTERN.match(right_tail):
            return False
    if left_key in right_key and len(right_cleaned.split()) <= len(left_cleaned.split()) + 1:
        return False
    return True


def _matching_pair_quality_score(left: str, right: str) -> int:
    """Score matching pairs to keep richer and more explicit associations."""

    left_words = len(left.split())
    right_words = len(right.split())
    score = (right_words * 10) + (min(left_words, 6) * 2)
    if "," in right:
        score += 2
    if MATCHING_PREDICATE_PREFIX_PATTERN.search(right):
        score += 1
    if MATCHING_WEAK_CERTAINTY_PATTERN.search(right):
        score -= 8
    return score


def _select_best_matching_pairs(
    candidates: list[tuple[int, str, str, int]],
    *,
    limit: int,
) -> list[tuple[str, str]]:
    if limit <= 0 or not candidates:
        return []

    ranked = sorted(candidates, key=lambda row: (-row[3], row[0]))
    selected: list[tuple[int, str, str]] = []
    seen_left: set[str] = set()
    seen_right: set[str] = set()

    for index, left, right, _score in ranked:
        left_id = _normalize_identifier(_strip_matching_leading_articles(left))
        right_id = _normalize_identifier(right)
        if not left_id or not right_id:
            continue
        if left_id in seen_left or right_id in seen_right:
            continue
        seen_left.add(left_id)
        seen_right.add(right_id)
        selected.append((index, left, right))
        if len(selected) >= limit:
            break

    selected.sort(key=lambda row: row[0])
    return [(left, right) for _, left, right in selected]


def _mcq_distractors(correct: str, distractors: list[str], answer_options: list[str]) -> list[str]:
    parsed = [value.strip() for value in distractors if value and value.strip()]
    if not parsed:
        parsed = [
            value.strip()
            for value in answer_options
            if value and value.strip() and value.strip() != correct
        ]
    seen: set[str] = set()
    deduped: list[str] = []
    for value in parsed:
        if value == correct or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _cloze_token(correct: str, distractors: list[str]) -> str:
    options: list[tuple[int, str]] = []
    safe_correct = correct.strip() or "Reponse attendue"
    options.append((100, safe_correct))
    seen = {safe_correct}
    for value in distractors:
        candidate = value.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        options.append((0, candidate))
    return "{:MULTICHOICE:" + "#~".join(f"%{fraction}%{text}" for fraction, text in options) + "}"


def _is_placeholder_cloze_option(value: str) -> bool:
    cleaned = _normalize_text(value)
    if not cleaned:
        return True
    if CLOZE_OPTION_PLACEHOLDER_PATTERN.match(cleaned):
        return True
    return cleaned.lower() in {"option a", "option b", "option c", "option d"}


def _parse_inline_cloze_token(token_payload: str) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for match in CLOZE_OPTION_PATTERN.finditer(token_payload):
        fraction = _normalize_text(match.group(1))
        text = _normalize_text(match.group(2))
        if text:
            parsed.append((fraction, text))
    return parsed


def _extract_prompt_candidate_terms(prompt: str) -> list[str]:
    text = _normalize_text(_strip_html(prompt))
    text = CLOZE_TOKEN_PATTERN.sub(" ", text)
    candidates: list[str] = []
    seen: set[str] = set()
    for token in CLOZE_WORD_PATTERN.findall(text):
        normalized = _normalize_text(token)
        key = normalized.lower()
        if key in CLOZE_STOPWORDS:
            continue
        if len(normalized) < 3:
            continue
        if key in seen:
            continue
        seen.add(key)
        candidates.append(normalized)
        if len(candidates) >= 30:
            break
    return candidates


def _build_cloze_fallback_distractors(
    *,
    correct: str,
    seed_values: list[str],
    prompt: str,
    limit: int = 3,
) -> list[str]:
    normalized_correct = _normalize_text(correct)
    seen = {normalized_correct.lower()} if normalized_correct else set()
    distractors: list[str] = []

    def push(candidate: str) -> None:
        normalized = _normalize_text(candidate)
        if not normalized:
            return
        key = normalized.lower()
        if key in seen:
            return
        if _is_placeholder_cloze_option(normalized):
            return
        seen.add(key)
        distractors.append(normalized)

    for seed in seed_values:
        push(seed)
        if len(distractors) >= limit:
            return distractors[:limit]

    for term in _extract_prompt_candidate_terms(prompt):
        push(term)
        if len(distractors) >= limit:
            return distractors[:limit]

    if len(distractors) < limit:
        base = normalized_correct or "reponse"
        push(f"{base} partielle")
        if len(distractors) < limit:
            push(f"{base} alternative")
        if len(distractors) < limit:
            push("hors contexte")

    return distractors[:limit]


def _repair_inline_cloze_tokens(
    *,
    prompt: str,
    expected_answers: list[str],
    distractor_pool: list[str],
) -> str:
    token_matches = list(CLOZE_TOKEN_PATTERN.finditer(prompt))
    if not token_matches:
        return prompt

    rebuilt_tokens: list[str] = []
    used_expected = 0

    for index, match in enumerate(token_matches):
        parsed_options = _parse_inline_cloze_token(match.group(1))
        parsed_correct = [
            text
            for fraction, text in parsed_options
            if fraction and fraction not in {"0", "0.0", "0,0"}
        ]
        correct = (
            parsed_correct[0]
            if parsed_correct
            else expected_answers[index]
            if index < len(expected_answers)
            else expected_answers[0]
            if expected_answers
            else "Reponse attendue"
        )
        if index < len(expected_answers):
            used_expected = index + 1

        parsed_distractors = [
            text
            for fraction, text in parsed_options
            if fraction in {"0", "0.0", "0,0"} and not _is_placeholder_cloze_option(text)
        ]
        seed_values = [
            *parsed_distractors,
            *expected_answers,
            *distractor_pool,
        ]
        distractors = _build_cloze_fallback_distractors(
            correct=correct,
            seed_values=seed_values,
            prompt=prompt,
            limit=3,
        )
        rebuilt_tokens.append(_cloze_token(correct, distractors))

    if used_expected < len(expected_answers):
        for answer in expected_answers[used_expected:]:
            distractors = _build_cloze_fallback_distractors(
                correct=answer,
                seed_values=[*expected_answers, *distractor_pool],
                prompt=prompt,
                limit=3,
            )
            rebuilt_tokens.append(_cloze_token(answer, distractors))

    iterator = iter(rebuilt_tokens)
    return CLOZE_TOKEN_PATTERN.sub(lambda _m: next(iterator), prompt, count=len(rebuilt_tokens))


def _build_cloze_text(prompt: str, correct_answers: list[str], distractors: list[str]) -> str:
    text = (prompt or "").strip()
    expected_answers = _dedupe_non_empty(correct_answers)
    distractor_pool = _dedupe_non_empty(
        [value for value in distractors if not _is_placeholder_cloze_option(value)]
    )

    if "{:MULTICHOICE:" in text:
        return _repair_inline_cloze_tokens(
            prompt=text,
            expected_answers=expected_answers,
            distractor_pool=distractor_pool,
        )

    if CLOZE_PLACEHOLDER_PATTERN.search(text):
        fallback_answers = expected_answers or ["Reponse attendue"]
        index = 0

        def replace_placeholder(_match: re.Match[str]) -> str:
            nonlocal index
            correct = (
                fallback_answers[index]
                if index < len(fallback_answers)
                else fallback_answers[-1]
            )
            index += 1
            token_distractors = _build_cloze_fallback_distractors(
                correct=correct,
                seed_values=[*fallback_answers, *distractor_pool],
                prompt=text,
                limit=3,
            )
            return _cloze_token(correct, token_distractors)

        return CLOZE_PLACEHOLDER_PATTERN.sub(replace_placeholder, text)

    primary_answer = expected_answers[0] if expected_answers else "Reponse attendue"
    token_distractors = _build_cloze_fallback_distractors(
        correct=primary_answer,
        seed_values=[*expected_answers, *distractor_pool],
        prompt=text,
        limit=3,
    )
    token = _cloze_token(primary_answer, token_distractors)
    if text:
        return f"{text} {token}".strip()
    return token


def _extract_matching_pairs(
    item_correct_answer: str | None, answer_options: list[str]
) -> list[tuple[str, str]]:
    def parse_chunks(chunks: list[str]) -> list[tuple[int, str, str, int]]:
        candidates: list[tuple[int, str, str, int]] = []
        seen_exact: set[tuple[str, str]] = set()
        sequence = 0
        for chunk in chunks:
            if not chunk:
                continue
            first_segments = [segment.strip() for segment in re.split(r"\s*(?:\|\||\n)+\s*", chunk) if segment.strip()]
            for segment in first_segments:
                candidate_fragments = [
                    part.strip()
                    for part in re.split(r"\s*;\s*(?=[^;]*(?:->|=>|=|→|-&gt;))", segment)
                    if part.strip()
                ]
                for candidate in candidate_fragments:
                    left: str | None = None
                    right: str | None = None
                    for separator in ("->", "=>", "→", "-&gt;", "="):
                        if separator in candidate:
                            raw_left, raw_right = candidate.split(separator, 1)
                            left = _normalize_matching_side(
                                _normalize_matching_left_candidate(raw_left),
                                max_words=8,
                                min_words=1,
                            )
                            if not left:
                                break
                            right = _coerce_matching_definition(left, raw_right)
                            break
                    if left is None and ":" in candidate:
                        raw_left, raw_right = candidate.split(":", 1)
                        left_candidate = _normalize_matching_side(
                            _normalize_matching_left_candidate(raw_left),
                            max_words=8,
                            min_words=1,
                        )
                        if (
                            left_candidate
                            and len(raw_left.strip()) <= 45
                            and "," not in raw_left
                            and "?" not in raw_left
                            and not MATCHING_LEFT_VERB_PATTERN.search(left_candidate)
                        ):
                            left = left_candidate
                            right = _coerce_matching_definition(left_candidate, raw_right)

                    if not left or not right:
                        continue
                    if not _is_valid_matching_pair(left, right):
                        continue
                    left = _normalize_matching_left_display(left)
                    key = (left.lower(), right.lower())
                    if key in seen_exact:
                        continue
                    seen_exact.add(key)
                    sequence += 1
                    candidates.append((sequence, left, right, _matching_pair_quality_score(left, right)))
        return candidates

    # Priorite aux paires validees dans correct_answer. Les answer_options servent
    # uniquement de secours si le bloc principal ne contient pas assez de paires.
    primary_chunks = [item_correct_answer] if item_correct_answer else []
    primary_selected = _select_best_matching_pairs(parse_chunks(primary_chunks), limit=12)
    if len(primary_selected) >= 2:
        return primary_selected

    fallback_chunks = [*primary_chunks, *answer_options]
    return _select_best_matching_pairs(parse_chunks(fallback_chunks), limit=12)


def _looks_like_matching_item(item_type_value: str, tags: list[str], correct: str, answer_options: list[str]) -> bool:
    if item_type_value == "matching":
        return True
    lowered_tags = {tag.strip().lower() for tag in tags if tag}
    if {"matching", "association_pairs", "association"} & lowered_tags:
        return True
    if "->" in correct:
        return True
    return any("->" in (option or "") for option in answer_options)


def _append_multichoice(rows: list[str], prompt: str, correct: str, distractors: list[str]) -> None:
    _append_multichoice_generic(
        rows=rows,
        prompt=prompt,
        correct_answers=[correct] if correct.strip() else [],
        distractors=distractors,
        single=True,
    )


def _append_multichoice_generic(
    *,
    rows: list[str],
    prompt: str,
    correct_answers: list[str],
    distractors: list[str],
    single: bool,
) -> None:
    if not correct_answers:
        return

    normalized_correct = _dedupe_non_empty(correct_answers)
    normalized_distractors = _dedupe_non_empty(distractors)
    if not normalized_correct:
        return

    answer_fraction = "100" if single or len(normalized_correct) <= 1 else str(
        max(1, round(100 / len(normalized_correct)))
    )

    rows.extend(
        [
            '<question type="multichoice">',
            f"  <name><text>{_cdata('')}</text></name>",
            '  <questiontext format="plain_text">',
            f"    <text>{_cdata(prompt)}</text>",
            "  </questiontext>",
            "  <externallink/>",
            "  <usecase>1</usecase>",
            "  <defaultgrade>1</defaultgrade>",
            "  <editeur>0</editeur>",
            f"  <single>{'true' if single else 'false'}</single>",
            "  <shuffleanswers>truez</shuffleanswers>",
        ]
    )
    for correct in normalized_correct:
        rows.extend(
            [
                f'  <answer fraction="{answer_fraction}" format="plain_text">',
                f"    <text>{_cdata(correct)}</text>",
                f"    <feedback><text>{_cdata('')}</text></feedback>",
                "  </answer>",
            ]
        )
    for distractor in normalized_distractors:
        rows.extend(
            [
                '  <answer fraction="0" format="plain_text">',
                f"    <text>{_cdata(distractor)}</text>",
                f"    <feedback><text>{_cdata('')}</text></feedback>",
                "  </answer>",
            ]
        )
    rows.append("</question>")


def _append_cloze(
    rows: list[str], prompt: str, correct_answers: list[str], distractors: list[str]
) -> None:
    cloze_text = _build_cloze_text(prompt, correct_answers, distractors)
    rows.extend(
        [
            '<question type="cloze" desc="variable">',
            f"  <name><text>{_cdata(_derive_name(prompt))}</text></name>",
            '  <questiontext format="html">',
            f"    <text>{_cdata(cloze_text)}</text>",
            "  </questiontext>",
            "  <externallink/>",
            "  <usecase>1</usecase>",
            "  <defaultgrade>1</defaultgrade>",
            "  <editeur>0</editeur>",
            "</question>",
        ]
    )


def _append_matching(rows: list[str], prompt: str, pairs: list[tuple[str, str]]) -> None:
    rows.extend(
        [
            '<question type="matching">',
            f"  <name><text>{_cdata(_derive_name(prompt))}</text></name>",
            '  <questiontext format="html">',
            f"    <text>{_cdata(prompt)}</text>",
            "  </questiontext>",
            "  <externallink/>",
            "  <usecase>1</usecase>",
            "  <defaultgrade>1</defaultgrade>",
            "  <editeur>0</editeur>",
        ]
    )
    for left, right in pairs:
        rows.extend(
            [
                "  <subquestion>",
                f"    <text>{_cdata(left)}</text>",
                "    <answer>",
                f"      <text>{_cdata(right)}</text>",
                "    </answer>",
                "  </subquestion>",
            ]
        )
    rows.extend(["  <shuffleanswers>true</shuffleanswers>", "</question>"])


def _validate_pronote_xml(xml_payload: str) -> None:
    root = ET.fromstring(xml_payload)
    for question in root.findall("question"):
        question_type = question.get("type", "")
        if question_type != "multichoice":
            continue
        answers = question.findall("answer")
        has_expected = False
        for answer in answers:
            fraction = (answer.get("fraction") or "").strip()
            text = _normalize_text(answer.findtext("text") or "")
            if text and fraction and fraction != "0":
                has_expected = True
                break
        if not has_expected:
            raise ValueError("Question multichoix invalide: reponse attendue manquante.")


class PronoteXmlExporter(BaseExporter):
    """PRONOTE exporter implementing strict XML order/fields requirements."""

    format_name = "pronote_xml"

    def export(
        self, content_set: ContentSetResponse, options: dict, output_dir: Path
    ) -> ExportArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = options.get("filename", f"content_{content_set.project_id}_pronote.xml")
        file_path = output_dir / filename

        name = options.get("name", "SkillBeam")
        answernumbering = options.get("answernumbering", "123")
        niveau = options.get("niveau", "")
        matiere = options.get("matiere", "")

        rows: list[str] = ['<?xml version="1.0" encoding="UTF-8" ?>', "<quiz>"]

        infos_xml = (
            "      <infos>\n"
            f"        <name>{name}</name>\n"
            f"        <answernumbering>{answernumbering}</answernumbering>\n"
            f"        <niveau>{niveau}</niveau>\n"
            f"        <matiere>{matiere}</matiere>\n"
            "      </infos>"
        )
        category_cdata = _cdata("\n" + infos_xml + "\n    ")

        rows.extend(
            [
                '<question type="category">',
                "  <category>",
                f"    <text>{category_cdata}</text>",
                "  </category>",
                "</question>",
            ]
        )

        exported_count = 0

        for item in content_set.items:
            prompt = _normalize_text(item.prompt or "")
            if not prompt:
                continue
            correct = _normalize_text(item.correct_answer or "")
            item_type = item.item_type.value
            item_tags = [tag for tag in item.tags if isinstance(tag, str)]
            answer_options = [value for value in item.answer_options if isinstance(value, str)]

            if item_type == "mcq":
                expected_answers = _split_expected_answers(correct)
                if not expected_answers:
                    fallback = _dedupe_non_empty(item.answer_options)
                    if fallback:
                        expected_answers = [fallback[0]]
                if not expected_answers:
                    continue
                mcq_correct = expected_answers[0]
                distractors = _mcq_distractors(mcq_correct, item.distractors, answer_options)
                _append_multichoice(rows, prompt=prompt, correct=mcq_correct, distractors=distractors)
                exported_count += 1
                continue

            if item_type == "poll":
                expected_answers = _split_expected_answers(correct)
                if not expected_answers:
                    continue
                options = _dedupe_non_empty([*answer_options, *item.distractors, *expected_answers])
                expected_lower = {value.lower() for value in expected_answers}
                distractors = [value for value in options if value.lower() not in expected_lower]
                if not distractors:
                    continue
                _append_multichoice_generic(
                    rows=rows,
                    prompt=prompt,
                    correct_answers=expected_answers,
                    distractors=distractors,
                    single=False,
                )
                exported_count += 1
                continue

            if item_type == "cloze":
                has_inline_token = "{:MULTICHOICE:" in prompt
                cloze_correct = _split_expected_answers(correct)
                if not has_inline_token and not cloze_correct:
                    continue
                seed_distractors = _dedupe_non_empty([*item.distractors, *answer_options])
                _append_cloze(
                    rows,
                    prompt=prompt,
                    correct_answers=cloze_correct,
                    distractors=seed_distractors,
                )
                exported_count += 1
                continue

            if _looks_like_matching_item(item_type, item_tags, correct, answer_options):
                pairs = _extract_matching_pairs(correct, answer_options)
                if len(pairs) >= 2:
                    _append_matching(rows, prompt=prompt, pairs=pairs)
                    exported_count += 1
                continue

        if exported_count == 0:
            raise ValueError("Aucune question exportable: ajoutez une reponse attendue pour chaque item.")

        rows.append("</quiz>")

        xml_payload = "\n".join(rows)
        _validate_pronote_xml(xml_payload)
        file_path.write_text(xml_payload, encoding="utf-8")
        return ExportArtifact(
            artifact_path=str(file_path), mime="application/xml", filename=filename
        )
