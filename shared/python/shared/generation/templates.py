"""Generation templates and guardrails."""

from __future__ import annotations

import json
import re
import unicodedata
from textwrap import dedent
from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, ValidationError

from shared.enums import ContentType, ItemType
from shared.llm.providers import LLMProvider
from shared.schemas import GeneratedItem

NOISY_SOURCE_LINE_PATTERN = re.compile(
    r"^\s*(source\s+(youtube|web)|lien|url|identifiant\s+video|transcription\s+(non\s+activee|indisponible)|generation\s+basee|recuperation\s+impossible|for\s+more\s+information\s+check|client\s+error|http\s+error|acces\s+refuse|access\s+denied)\b",
    flags=re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://\S+", flags=re.IGNORECASE)
PRONOTE_MODES_JSON_PREFIX = "PRONOTE_MODES_JSON:"
NUMERIC_VALUE_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")
NUMERIC_PROMPT_PATTERN = re.compile(
    r"\b(combien|nombre|valeur|annee|duree|distance|age|pourcentage|taux|note|score|quantite)\b",
    flags=re.IGNORECASE,
)
QUESTION_PREFIX_PATTERNS = [
    re.compile(r"^\s*item\s*#?\s*\d{1,3}\s*(?:[:.)-]\s*)", flags=re.IGNORECASE),
    re.compile(r"^\s*q\s*#?\s*\d{1,3}\s*(?:[:.)-]\s*|\s+)", flags=re.IGNORECASE),
    re.compile(
        r"^\s*question\s*(?:ouverte|open|qcm|a\s*saisir|numerique|texte\s*a\s*trous|association|choix\s*multiple|choix\s*unique)?\s*#?\s*\d{1,3}\s*(?:[:.)-]\s*|\s+)",
        flags=re.IGNORECASE,
    ),
    re.compile(r"^\s*texte\s*a\s*trous\s*#?\s*\d{1,3}\s*(?:[:.)-]\s*|\s+)", flags=re.IGNORECASE),
    re.compile(r"^\s*association\s*#?\s*\d{1,3}\s*(?:[:.)-]\s*|\s+)", flags=re.IGNORECASE),
    re.compile(r"^\s*\d{1,3}\s*[:.)-]\s*", flags=re.IGNORECASE),
]
MATCHING_PLACEHOLDER_PATTERN = re.compile(
    r"^(definition\s+de|element\s+[a-z0-9]+|notion\s+[a-z0-9]+|terme\s+[a-z0-9]+)\b",
    flags=re.IGNORECASE,
)
MATCHING_STOPWORDS: set[str] = {
    "comment",
    "pourquoi",
    "quelle",
    "quelles",
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
MATCHING_SENTENCE_PAIR_PATTERN = re.compile(
    r"^\s*(.+?)\s+\b(est|sont|decrit(?:e|ent)?|décrit(?:e|ent)?|signifie(?:nt)?|indique(?:nt)?|explique(?:nt)?|definit|définit|definissent|définissent|correspond(?:ent)?\s+a|permet(?:tent)?\s+de|sert(?:vent)?\s+a|consiste(?:nt)?\s+a|represente(?:nt)?|représente(?:nt)?|caracterise(?:nt)?|caractérise(?:nt)?|garantit|garantissent|envoie(?:nt)?|renvoie(?:nt)?|limite(?:nt)?|transmet(?:tent)?|recoi(?:t|vent)|reçoi(?:t|vent)|declenche(?:nt)?|déclenche(?:nt)?|active(?:nt)?)\b\s+(.+)$",
    flags=re.IGNORECASE,
)
MATCHING_CEST_A_DIRE_PAIR_PATTERN = re.compile(
    r"^\s*(.+?)\s*,?\s*c['’]?\s*est\s*[-–]?\s*[aà]\s*[-–]?\s*dire\s+(.+)$",
    flags=re.IGNORECASE,
)
MATCHING_LEADING_NOUN_PHRASE_PATTERN = re.compile(
    r"^\s*(?:l['’]|le|la|les|un|une|des)\s+([A-Za-zÀ-ÖØ-öø-ÿ0-9'-]+(?:\s+(?:de|d['’]|du|des|[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]+)){0,5})",
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
    r"^\s*(?:on\s+suppose(?:\s+que)?|on\s+considere(?:\s+que)?|on\s+considere(?:\s+que)?|"
    r"bien\s+entendu|ainsi|alors|dans\s+ce\s+cas|en\s+pratique)\b[,:-]?\s*",
    flags=re.IGNORECASE,
)
MATCHING_CEST_A_DIRE_PATTERN = re.compile(
    r"\bc['’]?\s*est\s*[-–]?\s*[aà]\s*[-–]?\s*dire\b",
    flags=re.IGNORECASE,
)
MATCHING_WEAK_CERTAINTY_PATTERN = re.compile(
    r"\b(probablement|s[ûu]rement)\b",
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
    "probablement",
    "surement",
    "sûrement",
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
    "qu",
    "quil",
    "quils",
    "vont",
    "mettre",
    "place",
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
    "paquet",
    "paquets",
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
MATCHING_DEFINITION_CUE_PATTERN = re.compile(
    r"\b(est|sont|signifie|signifient|correspond|correspondent|definit|définit|definissent|définissent|"
    r"explique|expliquent|indique|indiquent|represente|représente|representent|représentent|"
    r"caracterise|caractérise|caracterisent|caractérisent|decrit|décrit|decrivent|décrivent|"
    r"permet|permettent|sert|servent|garantit|garantissent|c['’]?\s*est\s*[-–]?\s*[aà]\s*[-–]?\s*dire)\b",
    flags=re.IGNORECASE,
)
MATCHING_RIGHT_MIN_WORDS = 5

PronoteMode = Literal[
    "single_choice",
    "multiple_choice",
    "numeric_value",
    "free_response",
    "spelling",
    "association_pairs",
    "cloze_free",
    "cloze_list_unique",
    "cloze_list_variable",
]
PRONOTE_MODES: set[PronoteMode] = {
    "single_choice",
    "multiple_choice",
    "numeric_value",
    "free_response",
    "spelling",
    "association_pairs",
    "cloze_free",
    "cloze_list_unique",
    "cloze_list_variable",
}


class LLMOutputModel(BaseModel):
    """Best-effort JSON payload from LLM providers."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)


class LLMMatchingPairsModel(BaseModel):
    """Optional strict payload for matching pairs refinement."""

    pairs: list[dict[str, Any]] = Field(default_factory=list)


CONTENT_TYPE_TO_ITEM_TYPE: dict[ContentType, ItemType] = {
    ContentType.COURSE_STRUCTURE: ItemType.COURSE_STRUCTURE,
    ContentType.MCQ: ItemType.MCQ,
    ContentType.POLL: ItemType.POLL,
    ContentType.OPEN_QUESTION: ItemType.OPEN_QUESTION,
    ContentType.CLOZE: ItemType.CLOZE,
    ContentType.MATCHING: ItemType.MATCHING,
    ContentType.BRAINSTORMING: ItemType.BRAINSTORMING,
    ContentType.FLASHCARDS: ItemType.FLASHCARD,
}

ITEM_TYPE_ALIASES: dict[str, ItemType] = {
    "mcq": ItemType.MCQ,
    "qcm": ItemType.MCQ,
    "multiple_choice": ItemType.MCQ,
    "multichoice": ItemType.MCQ,
    "single_choice": ItemType.MCQ,
    "quiz": ItemType.MCQ,
    "poll": ItemType.POLL,
    "survey": ItemType.POLL,
    "sondage": ItemType.POLL,
    "open_question": ItemType.OPEN_QUESTION,
    "question_ouverte": ItemType.OPEN_QUESTION,
    "open": ItemType.OPEN_QUESTION,
    "open_ended": ItemType.OPEN_QUESTION,
    "cloze": ItemType.CLOZE,
    "fill_in_the_blank": ItemType.CLOZE,
    "texte_a_trous": ItemType.CLOZE,
    "matching": ItemType.MATCHING,
    "association": ItemType.MATCHING,
    "associations": ItemType.MATCHING,
    "brainstorming": ItemType.BRAINSTORMING,
    "brainstorm": ItemType.BRAINSTORMING,
    "flashcard": ItemType.FLASHCARD,
    "flashcards": ItemType.FLASHCARD,
    "course_structure": ItemType.COURSE_STRUCTURE,
    "structure_de_cours": ItemType.COURSE_STRUCTURE,
    "plan_de_cours": ItemType.COURSE_STRUCTURE,
}


def build_prompt(
    *,
    source_text: str,
    content_types: list[ContentType],
    instructions: str | None,
    max_items: int,
    language: str,
    level: str,
    subject: str | None,
    class_level: str | None,
    difficulty_target: str | None,
) -> str:
    """Create strict JSON prompt for pedagogical generation."""

    types = ", ".join(ct.value for ct in content_types)
    extra = instructions.strip() if instructions else "Aucune instruction supplementaire."
    subject_value = subject.strip() if subject else "non precisee"
    class_value = class_level.strip() if class_level else level
    difficulty_value = difficulty_target.strip() if difficulty_target else "medium"
    class_value_normalized = class_value.lower()
    lycee_keywords = (
        "lycee",
        "2de",
        "seconde",
        "1ere",
        "premiere",
        "terminale",
        "bac",
    )
    lycee_wording_rule = (
        "- Niveau lycee: vocabulaire B1-B2, exemples concrets proches du quotidien scolaire, pas de jargon inutile."
        if any(keyword in class_value_normalized for keyword in lycee_keywords)
        else ""
    )
    cleaned_source = _sanitize_source_for_generation(source_text)
    excerpt = cleaned_source[:14000] if cleaned_source else source_text[:14000]

    return dedent(
        f"""
        Tu es un generateur de contenu pedagogique.
        Regles strictes:
        - Retourne UNIQUEMENT un JSON valide.
        - N'ajoute AUCUN markdown, aucune balise, aucun texte hors JSON.
        - Cle principale: items (liste), content_types (liste).
        - Limite: {max_items} items max.
        - Langue: {language}
        - Niveau: {level}
        - Matiere: {subject_value}
        - Classe cible: {class_value}
        - Difficulte cible: {difficulty_value}
        - Types demandes: {types}
        - Anti-hallucination: cite source_reference type 'section:X' quand possible.
        - Pour les QCM: 1 bonne reponse + 3 distracteurs minimum.
        - Pour les associations: format strict "Concept complet -> Definition complete" (pas de mots isoles).
        - Formulation eleve: enonce clair, phrase courte (idealement <= 22 mots), une seule idee evaluee par question.
        - Formulation eleve: evite les formulations floues ("idee principale de la section"), prefere des questions contextualisees et verifiables.
        - Formulation eleve: vocabulaire simple, direct, adapte a la classe cible; evite les doubles negations et les ambiguities.
        - Qualite pedagogique: distracteurs plausibles (erreurs frequentes d'eleves), jamais absurdes, jamais hors sujet.
        - Qualite pedagogique: reponse attendue concise et exploitable par un enseignant (sauf numerique/association/texte a trous).
        {lycee_wording_rule}
        - Structure item:
          {{
            "item_type": "mcq|open_question|poll|cloze|matching|brainstorming|flashcard|course_structure",
            "prompt": "question",
            "correct_answer": "reponse attendue",
            "distractors": ["...", "...", "..."],
            "answer_options": ["..."],
            "tags": ["..."],
            "difficulty": "easy|medium|hard",
            "feedback": "optionnel",
            "source_reference": "section:1"
          }}

        Instructions supplementaires:
        {extra}

        Source normalisee:
        {excerpt}
        """
    ).strip()


def generate_items(
    *,
    provider: LLMProvider,
    source_text: str,
    content_types: list[ContentType],
    instructions: str | None,
    max_items: int,
    language: str,
    level: str,
    subject: str | None = None,
    class_level: str | None = None,
    difficulty_target: str | None = None,
) -> list[GeneratedItem]:
    """Generate and validate pedagogical items."""

    effective_source = _sanitize_source_for_generation(source_text) or source_text
    prompt = build_prompt(
        source_text=effective_source,
        content_types=content_types,
        instructions=instructions,
        max_items=max_items,
        language=language,
        level=level,
        subject=subject,
        class_level=class_level,
        difficulty_target=difficulty_target,
    )

    llm_items = _attempt_llm_generation(
        provider=provider,
        prompt=prompt,
        content_types=content_types,
    )
    if not llm_items:
        retry_prompt = (
            prompt
            + "\n\nIMPORTANT: reponds strictement en JSON avec la cle racine 'items' "
            + "et une liste de questions pedagogiques concretes basees sur la source."
        )
        llm_items = _attempt_llm_generation(
            provider=provider,
            prompt=retry_prompt,
            content_types=content_types,
        )

    validated = _ensure_item_count(
        items=llm_items,
        source_text=effective_source,
        content_types=content_types,
        max_items=max_items,
    )
    pronote_mode_sequence = _extract_pronote_mode_sequence(
        instructions=instructions,
        max_items=max_items,
    )
    pairs_per_question = _extract_matching_pairs_per_question(instructions)
    should_refine_association_pairs = (
        ContentType.MATCHING in content_types
        or any(mode == "association_pairs" for mode in pronote_mode_sequence)
    )
    llm_matching_pool: list[tuple[str, str]] = []
    if should_refine_association_pairs:
        matching_count = sum(1 for mode in pronote_mode_sequence if mode == "association_pairs")
        association_target = max(
            8,
            matching_count * (pairs_per_question + 2),
            max_items * 2,
        )
        llm_matching_pool = _build_matching_llm_pairs_pool(
            provider=provider,
            source_text=effective_source,
            desired_pairs=association_target,
            language=language,
            level=level,
            subject=subject,
            class_level=class_level,
        )
    if pronote_mode_sequence:
        validated = _enforce_pronote_mode_coherence(
            items=validated,
            source_text=effective_source,
            mode_sequence=pronote_mode_sequence,
            llm_matching_pool=llm_matching_pool,
            pairs_per_question=pairs_per_question,
        )
    validated = _enforce_matching_item_coherence(
        items=validated,
        source_text=effective_source,
        llm_matching_pool=llm_matching_pool,
        pairs_per_question=pairs_per_question,
    )

    return [_sanitize_generated_item(item) for item in validated[:max_items]]


def _attempt_llm_generation(
    *,
    provider: LLMProvider,
    prompt: str,
    content_types: list[ContentType],
) -> list[GeneratedItem]:
    """Run one provider attempt and normalize JSON payload."""

    raw = provider.generate(prompt)
    parsed = _parse_llm_output(raw)
    return _coerce_generated_items(
        raw_items=parsed.items,
        requested_content_types=content_types,
    )


def _extract_json_block(raw: str) -> str:
    """Extract JSON object/array from provider response."""

    if not raw.strip():
        return raw

    fenced_match = re.search(
        r"```(?:json)?\s*([\[{].*?[\]}])\s*```", raw, flags=re.DOTALL | re.IGNORECASE
    )
    if fenced_match:
        return fenced_match.group(1).strip()

    object_start = raw.find("{")
    array_start = raw.find("[")
    starts = [position for position in (object_start, array_start) if position >= 0]
    if not starts:
        return raw

    start = min(starts)
    opener = raw[start]
    closer = "}" if opener == "{" else "]"
    end = raw.rfind(closer)
    if end > start:
        return raw[start : end + 1]
    return raw


def _parse_llm_output(raw: str) -> LLMOutputModel:
    """Parse LLM response into a tolerant intermediate payload."""

    try:
        payload = json.loads(_extract_json_block(raw))
    except json.JSONDecodeError:
        return LLMOutputModel(items=[])

    if isinstance(payload, list):
        payload = {"items": payload}
    if not isinstance(payload, dict):
        return LLMOutputModel(items=[])

    normalized_payload = dict(payload)
    items = normalized_payload.get("items")
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        for alias in ("questions", "results", "output", "data", "quiz"):
            candidate = normalized_payload.get(alias)
            if isinstance(candidate, list):
                items = candidate
                break
            if isinstance(candidate, dict):
                nested_items = candidate.get("items")
                if isinstance(nested_items, list):
                    items = nested_items
                    break
        if not isinstance(items, list):
            items = []

    content_types = normalized_payload.get("content_types")
    if isinstance(content_types, str):
        content_types = [content_types]
    if not isinstance(content_types, list):
        content_types = []

    try:
        return LLMOutputModel.model_validate({"items": items, "content_types": content_types})
    except ValidationError:
        return LLMOutputModel(items=[])


def _build_matching_llm_pairs_pool(
    *,
    provider: LLMProvider,
    source_text: str,
    desired_pairs: int,
    language: str,
    level: str,
    subject: str | None,
    class_level: str | None,
) -> list[tuple[str, str]]:
    """Generate high-quality association pairs with a dedicated LLM pass."""

    if desired_pairs <= 0:
        return []

    prepared_source = _sanitize_source_for_generation(source_text).strip()
    if not prepared_source:
        return []

    subject_value = subject.strip() if subject else "non precisee"
    class_value = class_level.strip() if class_level else level
    target_size = max(2, min(48, desired_pairs))
    excerpt = prepared_source[:14000]

    prompt = dedent(
        f"""
        Tu es un expert pedagogique. Construis des paires d'association coherentes pour des eleves.
        Retourne UNIQUEMENT un JSON valide de la forme:
        {{
          "pairs": [
            {{"left": "Notion complete", "right": "Definition complete et pedagogique"}},
            ...
          ]
        }}

        Contraintes strictes:
        - Produis exactement {target_size} paires, TOUTES DIFFERENTES entre elles.
        - CHAQUE paire doit porter sur une notion DISTINCTE. Ne jamais reformuler la meme notion.
        - left: notion disciplinaire complete (2 a 6 mots), sans verbe conjugue, sans fragment.
        - right: phrase complete de definition (10 a 24 mots), explicite, sans texte tronque.
        - right: NE COMMENCE JAMAIS par "est", "sont", "c'est" ou un verbe d'etat. Ecris directement une definition sous forme de groupe nominal ou phrase autonome.
          Exemple correct: "Transfert d'energie thermique par contact direct entre deux corps."
          Exemple incorrect: "Est un transfert d'energie thermique par contact."
        - TOUS les mots doivent etre COMPLETS. Jamais de mot coupe ou tronque. Jamais de lettre manquante.
        - Les accents doivent etre corrects : é, è, ê, à, ù, ç, etc.
        - right: la definition NE DOIT PAS contenir le terme exact de left ni un mot qui donne directement la reponse. L'eleve doit reflechir pour trouver l'association.
          Exemple correct: left="Signal sinusoidal", right="Forme d'onde periodique decrite par une fonction trigonometrique lisse"
          Exemple incorrect: left="Signal sinusoidal", right="Signal periodique dont la forme est sinusoidale"
        - Interdit dans left: mots de liaison, adverbes temporels, formulations narratives.
        - Evite les parentheses avec des symboles ou abreviations dans left et right.
        - Utilise les notions fondamentales presentes dans la source.
        - Verifie que chaque paire est unique et non redondante avant de la produire.
        - Langue: {language}
        - Niveau: {level}
        - Classe: {class_value}
        - Matiere: {subject_value}

        Source:
        {excerpt}
        """
    ).strip()

    pairs = _extract_matching_pairs_from_llm_payload(provider.generate(prompt), limit=target_size)
    if len(pairs) >= max(2, min(4, target_size)):
        return pairs

    retry_prompt = (
        prompt
        + "\nIMPORTANT: ne fournis que des notions disciplinaires concretes et des definitions completes. "
        + "Aucun mot isole, aucune phrase incomplete."
        + "\nNe commence AUCUNE definition par 'est' ou 'sont'. Chaque definition doit etre un groupe nominal autonome."
    )
    retry_pairs = _extract_matching_pairs_from_llm_payload(provider.generate(retry_prompt), limit=target_size)
    return retry_pairs if len(retry_pairs) > len(pairs) else pairs


def _extract_matching_pairs_from_llm_payload(raw: str, *, limit: int) -> list[tuple[str, str]]:
    """Parse and validate association pairs produced by the LLM."""

    if not raw.strip():
        return []

    try:
        payload = json.loads(_extract_json_block(raw))
    except json.JSONDecodeError:
        return []

    candidate_pairs: list[dict[str, Any]] = []
    if isinstance(payload, Mapping):
        raw_pairs = payload.get("pairs")
        if isinstance(raw_pairs, list):
            candidate_pairs = [row for row in raw_pairs if isinstance(row, Mapping)]
        elif isinstance(payload.get("items"), list):
            for row in payload.get("items", []):
                if isinstance(row, Mapping):
                    candidate_pairs.append(dict(row))
    elif isinstance(payload, list):
        for row in payload:
            if isinstance(row, Mapping):
                candidate_pairs.append(dict(row))

    try:
        parsed = LLMMatchingPairsModel.model_validate({"pairs": candidate_pairs})
    except ValidationError:
        return []

    scored: list[tuple[int, str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    sequence = 0
    for row in parsed.pairs:
        left_raw = ""
        right_raw = ""
        for key in ("left", "concept", "notion", "term", "element", "label"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                left_raw = value
                break
        for key in ("right", "definition", "description", "explanation", "answer"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                right_raw = value
                break
        if not left_raw or not right_raw:
            continue

        left = _normalize_matching_side(
            _normalize_matching_left_candidate(left_raw),
            max_words=8,
            min_words=1,
        )
        if not left:
            continue
        left = _normalize_matching_left_display(left)
        right = _coerce_matching_definition(left, right_raw)
        if not right:
            continue
        if not _is_valid_matching_pair(left, right):
            continue

        key = (left.lower(), right.lower())
        if key in seen:
            continue
        seen.add(key)
        sequence += 1
        scored.append((sequence, left, right, _matching_pair_quality_score(left, right)))

    return _select_best_matching_pairs(scored, limit=max(2, limit))


def _coerce_generated_items(
    *,
    raw_items: list[dict[str, Any]],
    requested_content_types: list[ContentType],
) -> list[GeneratedItem]:
    """Normalize provider payload item-by-item to avoid all-or-nothing fallback."""

    if not requested_content_types:
        default_item_type = ItemType.MCQ
    else:
        default_item_type = CONTENT_TYPE_TO_ITEM_TYPE.get(requested_content_types[0], ItemType.MCQ)

    generated_items: list[GeneratedItem] = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, Mapping):
            continue
        normalized = _normalize_item_payload(
            raw_item, default_item_type=default_item_type, position=index
        )
        if normalized is None:
            continue
        try:
            generated_items.append(GeneratedItem.model_validate(normalized))
        except ValidationError:
            continue
    return generated_items


def _normalize_item_payload(
    raw_item: Mapping[str, Any],
    *,
    default_item_type: ItemType,
    position: int,
) -> dict[str, Any] | None:
    """Map heterogeneous LLM item shapes to GeneratedItem schema."""

    item_type = _parse_item_type(
        _pick_first_key(raw_item, ("item_type", "type", "question_type", "content_type", "kind")),
        default_item_type=default_item_type,
    )
    prompt = _coerce_text(
        _pick_first_key(
            raw_item,
            ("prompt", "question", "question_text", "enonce", "statement", "text", "title"),
        )
    )
    if not prompt:
        return None

    correct_answer = _coerce_text(
        _pick_first_key(
            raw_item,
            ("correct_answer", "answer", "bonne_reponse", "expected_answer", "solution"),
        )
    )
    distractors = _coerce_string_list(
        _pick_first_key(
            raw_item,
            ("distractors", "wrong_answers", "incorrect_answers", "false_answers"),
        )
    )
    answer_options = _coerce_string_list(
        _pick_first_key(raw_item, ("answer_options", "options", "choices", "responses"))
    )
    tags = _coerce_string_list(raw_item.get("tags")) or [item_type.value]

    difficulty = (
        _coerce_text(_pick_first_key(raw_item, ("difficulty", "level", "difficulte"))) or "medium"
    ).lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    feedback = _coerce_text(_pick_first_key(raw_item, ("feedback", "explanation", "commentaire")))
    source_reference = _coerce_text(
        _pick_first_key(raw_item, ("source_reference", "source", "reference", "section"))
    )
    if source_reference and source_reference.isdigit():
        source_reference = f"section:{source_reference}"
    if not source_reference:
        source_reference = f"section:{position + 1}"

    if item_type == ItemType.MCQ:
        if not correct_answer and answer_options:
            correct_answer = answer_options[0]
        if answer_options and not distractors:
            distractors = [option for option in answer_options if option != correct_answer]
        distractors = _dedupe_strings(distractors)
        if len(distractors) < 3:
            distractors.extend(_default_mcq_distractors(existing=distractors))
        distractors = distractors[:3]
        answer_options = []

    if item_type == ItemType.POLL:
        poll_options = _dedupe_strings(answer_options or distractors)
        # No longer pad with "Option A/B/C" placeholders — empty polls
        # will be skipped at export time rather than emitted with junk.
        answer_options = poll_options[:6]
        correct_answer = None
        distractors = []

    return {
        "item_type": item_type.value,
        "prompt": prompt,
        "correct_answer": correct_answer,
        "distractors": _dedupe_strings(distractors),
        "answer_options": _dedupe_strings(answer_options),
        "tags": _dedupe_strings(tags),
        "difficulty": difficulty,
        "feedback": feedback,
        "source_reference": source_reference,
    }


def _parse_item_type(raw_value: Any, *, default_item_type: ItemType) -> ItemType:
    """Resolve item type from enum, canonical values or common aliases."""

    if isinstance(raw_value, ItemType):
        return raw_value

    if isinstance(raw_value, ContentType):
        return CONTENT_TYPE_TO_ITEM_TYPE.get(raw_value, default_item_type)

    normalized = _normalize_identifier(_coerce_text(raw_value) or "")
    if not normalized:
        return default_item_type
    if normalized in ITEM_TYPE_ALIASES:
        return ITEM_TYPE_ALIASES[normalized]
    if normalized.endswith("s") and normalized[:-1] in ITEM_TYPE_ALIASES:
        return ITEM_TYPE_ALIASES[normalized[:-1]]

    return default_item_type


def _pick_first_key(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    """Read first available value from key aliases in a mapping payload."""

    for key in keys:
        if key in payload:
            return payload[key]

    normalized_map: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(key, str):
            normalized_map[_normalize_identifier(key)] = value

    for key in keys:
        normalized = _normalize_identifier(key)
        if normalized in normalized_map:
            return normalized_map[normalized]
    return None


def _coerce_text(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        cleaned = raw_value.strip()
        return cleaned or None
    if isinstance(raw_value, (int, float)):
        return str(raw_value)
    if isinstance(raw_value, Mapping):
        for key in ("text", "value", "content", "label"):
            candidate = raw_value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _coerce_string_list(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        if not raw_value.strip():
            return []
        parts = re.split(r"[;\n|]+", raw_value)
        return _dedupe_strings([part.strip() for part in parts if part.strip()])
    if isinstance(raw_value, Mapping):
        text_candidate = _coerce_text(raw_value)
        return [text_candidate] if text_candidate else []
    if isinstance(raw_value, list):
        values: list[str] = []
        for entry in raw_value:
            text_candidate = _coerce_text(entry)
            if text_candidate:
                values.append(text_candidate)
        return _dedupe_strings(values)
    return []


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(cleaned)
    return deduped


def _default_mcq_distractors(*, existing: list[str]) -> list[str]:  # noqa: ARG001
    """Return an empty list — meta-text fallbacks are no longer used.

    Previously this returned generic phrases like "Une idee secondaire peu
    etayee" which leaked into the final XML as visible answer choices.
    Questions with insufficient distractors are now exported with fewer
    choices (which is valid for Pronote) rather than padded with junk text.
    """
    return []


def _normalize_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"[^a-z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _ensure_item_count(
    *,
    items: list[GeneratedItem],
    source_text: str,
    content_types: list[ContentType],
    max_items: int,
) -> list[GeneratedItem]:
    """Ensure generation returns enough items for requested max_items."""

    if max_items <= 0:
        return []
    if len(items) >= max_items:
        return items[:max_items]

    fallback_items = _rule_based_fallback(
        source_text=source_text,
        content_types=content_types,
        max_items=max_items,
    )
    if not items:
        return fallback_items[:max_items]

    merged = list(items)
    index = 0
    while len(merged) < max_items:
        template_item = fallback_items[index % len(fallback_items)]
        candidate = template_item
        if any(existing.prompt == template_item.prompt for existing in merged):
            candidate = template_item.model_copy(
                update={"prompt": f"{template_item.prompt} (variante {len(merged) + 1})"}
            )
        merged.append(candidate)
        index += 1

    return merged


def _rule_based_fallback(
    source_text: str, content_types: list[ContentType], max_items: int
) -> list[GeneratedItem]:
    """Fallback content generator used when provider output is invalid."""

    prepared_source = _sanitize_source_for_generation(source_text)
    sentences = _split_informative_sentences(prepared_source, minimum_length=24, limit=48)
    if not sentences:
        sentences = ["Le document presente des notions importantes."]

    types_cycle = content_types or [ContentType.MCQ]
    items: list[GeneratedItem] = []
    for index in range(max_items):
        number = index + 1
        content_type = types_cycle[index % len(types_cycle)]
        sentence = sentences[index % len(sentences)]

        if content_type == ContentType.MCQ:
            items.append(
                GeneratedItem(
                    item_type=ItemType.MCQ,
                    prompt=f"Q{number}. Quelle proposition resume le mieux: {sentence[:120]} ?",
                    correct_answer=sentence,
                    distractors=[
                        f"Une idee annexe non traitee ({number})",
                        f"Une conclusion sans lien direct ({number})",
                        f"Un exemple contradictoire ({number})",
                    ],
                    tags=["auto"],
                    difficulty="medium",
                    source_reference=f"section:{(index % len(sentences)) + 1}",
                )
            )
        elif content_type == ContentType.OPEN_QUESTION:
            items.append(
                GeneratedItem(
                    item_type=ItemType.OPEN_QUESTION,
                    prompt=f"Question ouverte {number}: explique en detail: {sentence}",
                    correct_answer="Attendus: definition, exemple, conclusion critique.",
                    tags=["open"],
                    difficulty="medium",
                    source_reference=f"section:{(index % len(sentences)) + 1}",
                )
            )
        elif content_type == ContentType.FLASHCARDS:
            items.append(
                GeneratedItem(
                    item_type=ItemType.FLASHCARD,
                    prompt=f"Carte {number}: notion cle",
                    correct_answer=sentence,
                    tags=["flashcard"],
                    difficulty="easy",
                    source_reference=f"section:{(index % len(sentences)) + 1}",
                )
            )
        elif content_type == ContentType.POLL:
            items.append(
                GeneratedItem(
                    item_type=ItemType.POLL,
                    prompt=f"Sondage {number}: quel angle est le plus pertinent pour '{sentence[:60]}' ?",
                    answer_options=[
                        "Approche theorique",
                        "Approche pratique",
                        "Approche critique",
                    ],
                    tags=["poll"],
                    difficulty="easy",
                    source_reference=f"section:{(index % len(sentences)) + 1}",
                )
            )
        elif content_type == ContentType.CLOZE:
            items.append(
                GeneratedItem(
                    item_type=ItemType.CLOZE,
                    prompt=f"Texte a trous {number}: complete: {sentence[:100]} ____.",
                    correct_answer="mot-cle",
                    tags=["cloze"],
                    difficulty="medium",
                    source_reference=f"section:{(index % len(sentences)) + 1}",
                )
            )
        elif content_type == ContentType.MATCHING:
            matching_pairs = _build_matching_fallback_pairs(
                source_text=prepared_source,
                desired_pairs=4,
            )
            matching_payload = " || ".join(f"{left} -> {right}" for left, right in matching_pairs)
            items.append(
                GeneratedItem(
                    item_type=ItemType.MATCHING,
                    prompt=f"Associez chaque notion a sa definition (contexte: {sentence[:90]}).",
                    correct_answer=matching_payload,
                    answer_options=[f"{left} -> {right}" for left, right in matching_pairs],
                    tags=["matching"],
                    difficulty="medium",
                    source_reference=f"section:{(index % len(sentences)) + 1}",
                )
            )
        elif content_type == ContentType.BRAINSTORMING:
            items.append(
                GeneratedItem(
                    item_type=ItemType.BRAINSTORMING,
                    prompt=f"Brainstorming {number}: propose 5 idees liees a: {sentence[:90]}",
                    correct_answer="Categories: causes, effets, applications",
                    tags=["brainstorming"],
                    difficulty="easy",
                    source_reference=f"section:{(index % len(sentences)) + 1}",
                )
            )
        else:
            items.append(
                GeneratedItem(
                    item_type=ItemType.COURSE_STRUCTURE,
                    prompt=f"Structure {number} proposee pour {content_type.value}",
                    correct_answer=f"1) Introduction 2) Concepts cles 3) Exercices sur: {sentence[:80]}",
                    tags=[content_type.value],
                    difficulty="medium",
                    source_reference=f"section:{(index % len(sentences)) + 1}",
                )
            )
    return items


def _sanitize_source_for_generation(source_text: str) -> str:
    """Remove noisy technical lines and URLs from source text."""

    if not source_text.strip():
        return source_text

    is_youtube_payload = bool(
        re.search(r"^\s*source\s+youtube\s*:", source_text, flags=re.IGNORECASE | re.MULTILINE)
    )
    kept_lines: list[str] = []
    for raw_line in source_text.splitlines():
        line = raw_line.strip()
        if not line:
            kept_lines.append("")
            continue
        if NOISY_SOURCE_LINE_PATTERN.match(line):
            continue
        if is_youtube_payload and re.match(r"^\s*(titre|chaine)\s*:", line, flags=re.IGNORECASE):
            continue
        line = URL_PATTERN.sub("", line).strip()
        if line:
            kept_lines.append(line)

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def _sanitize_generated_item(item: GeneratedItem) -> GeneratedItem:
    """Strip URLs/source prefixes from generated item fields for better readability."""

    cleaned_prompt = _clean_generated_field(item.prompt) or item.prompt
    return item.model_copy(
        update={
            "prompt": _strip_question_prefix(cleaned_prompt),
            "correct_answer": _clean_generated_field(item.correct_answer),
            "distractors": [_clean_generated_field(value) for value in item.distractors],
            "answer_options": [_clean_generated_field(value) for value in item.answer_options],
            "feedback": _clean_generated_field(item.feedback),
        }
    )


def _clean_generated_field(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = URL_PATTERN.sub("", value)
    cleaned = re.sub(r"\bsource\s+(youtube|web)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bidentifiant\s+video\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(titre|chaine)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\brecuperation\s+impossible\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfor\s+more\s+information\s+check\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(client|http)\s+error\s*['\"]?\d{3}[^:]*:\s*", "", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned or value.strip()


def _extract_pronote_mode_sequence(*, instructions: str | None, max_items: int) -> list[PronoteMode]:
    """Read machine-readable Pronote mode distribution from instructions."""

    if not instructions or max_items <= 0:
        return []

    raw_payload: str | None = None
    for line in instructions.splitlines():
        stripped = line.strip()
        if stripped.startswith(PRONOTE_MODES_JSON_PREFIX):
            raw_payload = stripped[len(PRONOTE_MODES_JSON_PREFIX) :].strip()
            break
    if not raw_payload:
        prefix_idx = instructions.lower().find(PRONOTE_MODES_JSON_PREFIX.lower())
        if prefix_idx >= 0:
            tail = instructions[prefix_idx + len(PRONOTE_MODES_JSON_PREFIX) :].lstrip()
            brace_idx = tail.find("{")
            if brace_idx >= 0:
                tail = tail[brace_idx:]
                decoder = json.JSONDecoder()
                try:
                    decoded_inline, _ = decoder.raw_decode(tail)
                except json.JSONDecodeError:
                    decoded_inline = None
                if isinstance(decoded_inline, Mapping):
                    decoded = decoded_inline
                else:
                    return []
            else:
                return []
        else:
            return []
    else:
        try:
            decoded = json.loads(raw_payload)
        except json.JSONDecodeError:
            return []
        if not isinstance(decoded, Mapping):
            return []

    sequence: list[PronoteMode] = []
    for raw_mode, raw_count in decoded.items():
        mode_name = _normalize_identifier(str(raw_mode))
        if mode_name not in PRONOTE_MODES:
            continue
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        count = min(100, count)
        sequence.extend([mode_name] * count)  # type: ignore[list-item]

    return sequence[:max_items]


def _extract_matching_pairs_per_question(instructions: str | None) -> int:
    """Read matching_pairs_per_question from PRONOTE_MODES_JSON in instructions."""
    if not instructions:
        return 3
    for line in instructions.splitlines():
        stripped = line.strip()
        if stripped.startswith(PRONOTE_MODES_JSON_PREFIX):
            raw = stripped[len(PRONOTE_MODES_JSON_PREFIX):].strip()
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                return 3
            if isinstance(decoded, Mapping):
                val = decoded.get("matching_pairs_per_question")
                if val is not None:
                    try:
                        return max(2, min(6, int(val)))
                    except (TypeError, ValueError):
                        pass
            return 3
    return 3


def _enforce_pronote_mode_coherence(
    *,
    items: list[GeneratedItem],
    source_text: str,
    mode_sequence: list[PronoteMode],
    llm_matching_pool: list[tuple[str, str]] | None = None,
    pairs_per_question: int = 3,
) -> list[GeneratedItem]:
    """Force minimal coherence between selected Pronote mode and generated item shape."""

    if not items or not mode_sequence:
        return items

    matching_mode_count = sum(1 for mode in mode_sequence if mode == "association_pairs")
    matching_pool: list[tuple[str, str]] = []
    if matching_mode_count > 0:
        desired_pool_size = max(6, matching_mode_count * (pairs_per_question + 2))
        if llm_matching_pool:
            matching_pool = _select_matching_pairs_variant(
                llm_matching_pool,
                variant_index=0,
                desired_pairs=desired_pool_size,
            )
        if len(matching_pool) < 2:
            matching_pool = _build_matching_fallback_pairs(
                source_text=_sanitize_source_for_generation(source_text),
                desired_pairs=desired_pool_size,
            )
    matching_index = 0
    # Track globally consumed pairs to avoid duplicates across questions.
    used_pair_keys: set[tuple[str, str]] = set()

    coerced: list[GeneratedItem] = []
    for index, item in enumerate(items):
        if index >= len(mode_sequence):
            coerced.append(item)
            continue
        mode = mode_sequence[index]

        # For association questions, filter pool to exclude already-used pairs.
        if mode == "association_pairs" and matching_pool:
            available_pool = [
                p for p in matching_pool
                if (p[0].strip().lower(), p[1].strip().lower()) not in used_pair_keys
            ]
            if len(available_pool) < 2:
                available_pool = matching_pool  # fallback: allow reuse
        else:
            available_pool = matching_pool

        result = _coerce_item_for_pronote_mode(
            item=item,
            mode=mode,
            source_text=source_text,
            association_pool=available_pool if mode == "association_pairs" else matching_pool,
            association_index=matching_index,
            association_total=matching_mode_count,
            pairs_per_question=pairs_per_question,
        )
        coerced.append(result)
        if mode == "association_pairs":
            # Mark pairs from this question as used.
            for opt in result.answer_options:
                for sep in ("->", "=>", "→"):
                    if sep in opt:
                        raw_l, raw_r = opt.split(sep, 1)
                        used_pair_keys.add((raw_l.strip().lower(), raw_r.strip().lower()))
                        break
            matching_index += 1
    return coerced


def _looks_like_matching_item_payload(item: GeneratedItem) -> bool:
    if item.item_type == ItemType.MATCHING:
        return True
    normalized_tags = {_normalize_identifier(tag) for tag in item.tags}
    if {"matching", "association", "association_pairs"} & normalized_tags:
        return True
    correct = item.correct_answer or ""
    if any(token in correct for token in ("->", "=>", "→", "-&gt;")):
        return True
    return any(any(token in option for token in ("->", "=>", "→", "-&gt;")) for option in item.answer_options)


def _enforce_matching_item_coherence(
    *,
    items: list[GeneratedItem],
    source_text: str,
    pairs_per_question: int = 3,
    llm_matching_pool: list[tuple[str, str]] | None = None,
) -> list[GeneratedItem]:
    if not items:
        return items

    matching_indexes = [index for index, item in enumerate(items) if _looks_like_matching_item_payload(item)]
    if not matching_indexes:
        return items

    desired_pool_size = max(8, len(matching_indexes) * (pairs_per_question + 2))
    matching_pool: list[tuple[str, str]] = []
    if llm_matching_pool:
        matching_pool = _select_matching_pairs_variant(
            llm_matching_pool,
            variant_index=0,
            desired_pairs=desired_pool_size,
        )
    if len(matching_pool) < 2:
        matching_pool = _build_matching_fallback_pairs(
            source_text=_sanitize_source_for_generation(source_text),
            desired_pairs=desired_pool_size,
        )
    matching_index = 0
    coerced: list[GeneratedItem] = []
    # Track globally consumed pairs to avoid duplicates across questions.
    used_pair_keys: set[tuple[str, str]] = set()

    for item in items:
        if not _looks_like_matching_item_payload(item):
            coerced.append(item)
            continue

        normalized_tags = {_normalize_identifier(tag) for tag in item.tags}
        extracted_pairs = _extract_matching_pairs(item=item, source_text=source_text)
        is_pronote_matching = bool(
            {"pronote", "association_pairs"} & normalized_tags
            or any(tag in PRONOTE_MODES for tag in normalized_tags)
        )
        if is_pronote_matching and _matching_pairs_are_pronote_ready(extracted_pairs):
            # Filter out globally used pairs before accepting pronote-ready items.
            filtered_pairs = [
                p for p in extracted_pairs
                if (p[0].strip().lower(), p[1].strip().lower()) not in used_pair_keys
            ]
            if len(filtered_pairs) < 2:
                filtered_pairs = extracted_pairs  # fallback: allow reuse
            tags = ["matching", *item.tags]
            if "association_pairs" in normalized_tags or "pronote" in normalized_tags:
                tags.append("association_pairs")
            deduped_tags = _dedupe_strings(tags)
            prompt = _strip_question_prefix(item.prompt or "").strip()
            if not re.search(r"\bassoc(?:ier|iez|iation)\b", prompt, flags=re.IGNORECASE):
                prompt = "Associez chaque notion du texte a sa definition ou a sa caracteristique correspondante."
            coerced.append(
                item.model_copy(
                    update={
                        "item_type": ItemType.MATCHING,
                        "prompt": _ensure_question_mark(prompt),
                        "correct_answer": " || ".join(f"{left} -> {right}" for left, right in filtered_pairs),
                        "distractors": [],
                        "answer_options": [f"{left} -> {right}" for left, right in filtered_pairs],
                        "tags": deduped_tags,
                    }
                )
            )
            for left, right in filtered_pairs:
                used_pair_keys.add((left.strip().lower(), right.strip().lower()))
            matching_index += 1
            continue

        if _matching_pairs_need_fallback(extracted_pairs):
            extracted_pairs = []

        pair_pool_size = len(extracted_pairs if extracted_pairs else matching_pool)
        # Use the user-configured pairs_per_question, fall back to 2 if pool is too small.
        min_needed = (len(matching_indexes) - 1) * pairs_per_question + 2
        desired_pairs = pairs_per_question if pair_pool_size >= min_needed else max(2, pairs_per_question - 1)

        # Filter pool to exclude globally used pairs.
        active_pool = extracted_pairs if extracted_pairs else matching_pool
        available_pool = [
            p for p in active_pool
            if (p[0].strip().lower(), p[1].strip().lower()) not in used_pair_keys
        ]
        if len(available_pool) < desired_pairs:
            available_pool = active_pool  # fallback: allow reuse if pool exhausted

        pairs = _select_matching_pairs_variant(
            available_pool,
            variant_index=matching_index,
            desired_pairs=desired_pairs,
        )
        if len(pairs) < 2 and matching_pool:
            available_fallback = [
                p for p in matching_pool
                if (p[0].strip().lower(), p[1].strip().lower()) not in used_pair_keys
            ]
            if len(available_fallback) < 2:
                available_fallback = matching_pool
            pairs = _select_matching_pairs_variant(
                available_fallback,
                variant_index=matching_index,
                desired_pairs=desired_pairs,
            )
        if len(pairs) < 2:
            pairs = [
                ("Concept principal", "Definition complete basee sur le texte source."),
                ("Notion cle", "Lien explicite avec le contenu pedagogique fourni."),
                ("Exemple concret", "Illustration precise qui aide a valider la comprehension."),
            ]

        tags = ["matching", *item.tags]
        if (
            "pronote" in normalized_tags
            or "association_pairs" in normalized_tags
            or any(tag in PRONOTE_MODES for tag in normalized_tags)
        ):
            tags.append("association_pairs")
        deduped_tags = _dedupe_strings(tags)
        prompt = _strip_question_prefix(item.prompt or "").strip()
        if not re.search(r"\bassoc(?:ier|iez|iation)\b", prompt, flags=re.IGNORECASE):
            prompt = "Associez chaque notion du texte a sa definition ou a sa caracteristique correspondante."

        coerced.append(
            item.model_copy(
                update={
                    "item_type": ItemType.MATCHING,
                    "prompt": _ensure_question_mark(prompt),
                    "correct_answer": " || ".join(f"{left} -> {right}" for left, right in pairs),
                    "distractors": [],
                    "answer_options": [f"{left} -> {right}" for left, right in pairs],
                    "tags": deduped_tags,
                }
            )
        )
        for left, right in pairs:
            used_pair_keys.add((left.strip().lower(), right.strip().lower()))
        matching_index += 1

    return coerced


def _coerce_item_for_pronote_mode(
    *,
    item: GeneratedItem,
    mode: PronoteMode,
    source_text: str,
    association_pool: list[tuple[str, str]] | None = None,
    association_index: int = 0,
    association_total: int = 1,
    pairs_per_question: int = 3,
) -> GeneratedItem:
    """Adapt a generated item to the target Pronote exercise mode."""

    prompt = _strip_question_prefix(item.prompt or "").strip()
    tags = _dedupe_strings([*item.tags, "pronote", mode])
    difficulty = item.difficulty if item.difficulty in {"easy", "medium", "hard"} else "medium"

    if mode == "single_choice":
        correct = _normalize_short_text(item.correct_answer) or _pick_first_text(
            item.answer_options
        ) or "Reponse attendue"
        distractors = _coerce_mcq_distractors(item=item, correct=correct)
        return item.model_copy(
            update={
                "item_type": ItemType.MCQ,
                "prompt": _ensure_question_mark(prompt),
                "correct_answer": correct,
                "distractors": distractors,
                "answer_options": [],
                "tags": tags,
                "difficulty": difficulty,
            }
        )

    if mode == "multiple_choice":
        options = _coerce_poll_options(item=item)
        expected_answers = _coerce_multiple_choice_expected_answers(
            raw_expected=item.correct_answer,
            options=options,
        )
        return item.model_copy(
            update={
                "item_type": ItemType.POLL,
                "prompt": _ensure_question_mark(prompt),
                "correct_answer": " || ".join(expected_answers),
                "distractors": [],
                "answer_options": options,
                "tags": tags,
                "difficulty": difficulty,
            }
        )

    if mode == "numeric_value":
        numeric_answer = _extract_numeric_answer(
            item.correct_answer or "",
            prompt,
            source_text,
        )
        numeric_prompt = prompt
        if not NUMERIC_PROMPT_PATTERN.search(numeric_prompt):
            numeric_prompt = (
                f"Saisissez la valeur numerique attendue (chiffres uniquement): {prompt}"
                if prompt
                else "Saisissez la valeur numerique attendue (chiffres uniquement)."
            )
        return item.model_copy(
            update={
                "item_type": ItemType.OPEN_QUESTION,
                "prompt": _ensure_question_mark(numeric_prompt),
                "correct_answer": numeric_answer,
                "distractors": [],
                "answer_options": [],
                "tags": tags,
                "difficulty": difficulty,
            }
        )

    if mode == "free_response":
        expected = _normalize_short_text(item.correct_answer)
        if expected and NUMERIC_VALUE_PATTERN.fullmatch(expected):
            expected = None
        expected = expected or "Reponse textuelle courte attendue d'apres le texte."
        return item.model_copy(
            update={
                "item_type": ItemType.OPEN_QUESTION,
                "prompt": _ensure_question_mark(prompt),
                "correct_answer": expected,
                "distractors": [],
                "answer_options": [],
                "tags": tags,
                "difficulty": difficulty,
            }
        )

    if mode == "spelling":
        base_prompt = prompt or "Epelez correctement le mot attendu."
        if "epel" not in base_prompt.lower():
            base_prompt = f"Epelez correctement: {base_prompt}"
        spelling_answer = _extract_spelling_answer(
            item.correct_answer or "",
            source_text,
        )
        return item.model_copy(
            update={
                "item_type": ItemType.OPEN_QUESTION,
                "prompt": _ensure_question_mark(base_prompt),
                "correct_answer": spelling_answer,
                "distractors": [],
                "answer_options": [],
                "tags": tags,
                "difficulty": difficulty,
            }
        )

    if mode == "association_pairs":
        desired_pairs = pairs_per_question
        extracted_pairs = _extract_matching_pairs(item=item, source_text=source_text)
        if (
            not _matching_pairs_are_exportable(extracted_pairs)
            or _matching_pairs_need_fallback(extracted_pairs)
            or not _matching_pairs_are_pronote_ready(extracted_pairs)
        ):
            extracted_pairs = []
        source_pairs = association_pool or _build_matching_fallback_pairs(
            source_text=_sanitize_source_for_generation(source_text),
            desired_pairs=8,
        )
        pair_pool = extracted_pairs if extracted_pairs else source_pairs
        pairs = _select_matching_pairs_variant(
            pair_pool,
            variant_index=association_index,
            desired_pairs=desired_pairs,
        )
        if len(pairs) < 2 and extracted_pairs and source_pairs:
            pairs = _select_matching_pairs_variant(
                source_pairs,
                variant_index=association_index,
                desired_pairs=desired_pairs,
            )
        if not _matching_pairs_are_pronote_ready(pairs) and source_pairs:
            pairs = _select_matching_pairs_variant(
                source_pairs,
                variant_index=association_index,
                desired_pairs=desired_pairs,
            )
        if not _matching_pairs_are_pronote_ready(pairs):
            pairs = [
                pair
                for pair in pairs
                if _is_valid_matching_pair(pair[0], pair[1]) and len(pair[1].split()) >= 4
            ]
        if not _matching_pairs_are_pronote_ready(pairs):
            pairs = [
                ("Concept principal", "Definition complete basee sur le texte source."),
                ("Notion cle", "Lien explicite avec le contenu pedagogique fourni."),
                ("Exemple concret", "Illustration precise qui aide a valider la comprehension."),
            ]
        formatted_pairs = " || ".join(f"{left} -> {right}" for left, right in pairs)
        preserved_tags = [
            tag
            for tag in item.tags
            if _normalize_identifier(tag)
            not in {
                "mcq",
                "open_question",
                "poll",
                "cloze",
                "matching",
                "flashcard",
                "course_structure",
                "brainstorming",
            }
        ]
        association_tags = _dedupe_strings([*preserved_tags, "matching", "pronote", "association_pairs"])
        association_prompt = _build_association_prompt_from_pairs(pairs)
        return item.model_copy(
            update={
                "item_type": ItemType.MATCHING,
                "prompt": _ensure_question_mark(association_prompt),
                "correct_answer": formatted_pairs,
                "distractors": [],
                "answer_options": [f"{left} -> {right}" for left, right in pairs],
                "tags": association_tags,
                "difficulty": difficulty,
            }
        )

    if mode in {"cloze_free", "cloze_list_unique", "cloze_list_variable"}:
        cloze_prompt = prompt
        if "____" not in cloze_prompt and "{:MULTICHOICE:" not in cloze_prompt:
            cloze_prompt = f"{cloze_prompt.rstrip(' .')} ____.".strip() if cloze_prompt else "Completez: ____."
        correct = _normalize_short_text(item.correct_answer) or _extract_spelling_answer("", source_text)
        distractors = _dedupe_strings([*item.distractors, *item.answer_options])
        if mode == "cloze_free":
            distractors = []
        else:
            distractors = [value for value in distractors if value.lower() != correct.lower()]
            if len(distractors) < 3:
                distractors.extend(_default_mcq_distractors(existing=distractors))
            distractors = distractors[:3]
        return item.model_copy(
            update={
                "item_type": ItemType.CLOZE,
                "prompt": cloze_prompt,
                "correct_answer": correct,
                "distractors": distractors,
                "answer_options": [],
                "tags": tags,
                "difficulty": difficulty,
            }
        )

    return item


def _select_matching_pairs_variant(
    pairs: list[tuple[str, str]],
    *,
    variant_index: int,
    desired_pairs: int,
) -> list[tuple[str, str]]:
    """Select a stable subset of matching pairs while varying items across variants."""

    if desired_pairs <= 0:
        return []

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for left, right in pairs:
        key = (left.strip().lower(), right.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append((left, right))
    if not deduped:
        return []
    if len(deduped) <= desired_pairs:
        # Keep stable output but rotate ordering across variants so multi-item
        # association generation does not repeat the exact same payload string.
        if len(deduped) <= 1:
            return deduped
        offset = variant_index % len(deduped)
        return deduped[offset:] + deduped[:offset]

    selected: list[tuple[str, str]] = []
    start = (variant_index * desired_pairs) % len(deduped)
    cursor = start
    attempts = 0
    while len(selected) < desired_pairs and attempts < len(deduped) * 2:
        pair = deduped[cursor % len(deduped)]
        if pair not in selected:
            selected.append(pair)
        cursor += 1
        attempts += 1

    if len(selected) < desired_pairs:
        for pair in deduped:
            if pair in selected:
                continue
            selected.append(pair)
            if len(selected) >= desired_pairs:
                break

    return selected[:desired_pairs]


def _strip_question_prefix(value: str) -> str:
    next_value = value.strip()
    changed = True
    while changed:
        changed = False
        for pattern in QUESTION_PREFIX_PATTERNS:
            cleaned = pattern.sub("", next_value, count=1).lstrip()
            if cleaned != next_value:
                next_value = cleaned
                changed = True
    return next_value


def _ensure_question_mark(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    if text.endswith("?"):
        return text
    if text.endswith((".", "!", ";", ":")):
        text = text.rstrip(".!;:")
    return f"{text} ?"


def _normalize_short_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return None
    cleaned = re.sub(r"^\s*reponse\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned or None


def _pick_first_text(values: list[str]) -> str | None:
    for value in values:
        cleaned = _normalize_short_text(value)
        if cleaned:
            return cleaned
    return None


def _coerce_mcq_distractors(*, item: GeneratedItem, correct: str) -> list[str]:
    distractors = _dedupe_strings(
        [
            *item.distractors,
            *[option for option in item.answer_options if option.strip().lower() != correct.lower()],
        ]
    )
    if len(distractors) < 3:
        distractors.extend(_default_mcq_distractors(existing=distractors))
    return distractors[:3]


def _coerce_poll_options(*, item: GeneratedItem) -> list[str]:
    options = _dedupe_strings([*item.answer_options, *item.distractors])
    if item.correct_answer:
        options = _dedupe_strings(
            [
                *options,
                *[
                    part.strip()
                    for part in re.split(r"\|\||;|\n", item.correct_answer)
                    if part and part.strip()
                ],
            ]
        )
    return _dedupe_strings(options)[:6]


def _coerce_multiple_choice_expected_answers(*, raw_expected: str | None, options: list[str]) -> list[str]:
    expected = _dedupe_strings(
        [
            part.strip()
            for part in re.split(r"\|\||;|\n", raw_expected or "")
            if part and part.strip()
        ]
    )
    if not expected and options:
        expected = options[: min(2, len(options))]
    if len(expected) == 1 and len(options) >= 2:
        for option in options:
            if option.strip().lower() != expected[0].strip().lower():
                expected.append(option)
                break
    return expected[:3]


def _extract_numeric_answer(*texts: str) -> str:
    for text in texts:
        for match in NUMERIC_VALUE_PATTERN.finditer(text or ""):
            candidate = match.group(0).replace(",", ".").strip()
            if candidate:
                return candidate
    return "1"


def _extract_spelling_answer(correct_answer: str, source_text: str) -> str:
    for text in (correct_answer, source_text):
        for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text or ""):
            lowered = token.lower()
            if lowered in {"quelle", "quelles", "comment", "pourquoi", "avec", "dans", "sans"}:
                continue
            return token
    return "mot"


def _split_informative_sentences(
    source_text: str, *, minimum_length: int = 24, limit: int = 64
) -> list[str]:
    """Split source text into deduped informative sentence-like fragments."""

    if not source_text.strip():
        return []

    chunks = re.split(r"(?:[.!?]\s+|\n+)", source_text.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        sentence = re.sub(r"\s+", " ", chunk).strip(" -:;,.")
        if len(sentence) < minimum_length:
            continue
        if len(sentence.split()) < 5:
            continue
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sentence)
        if len(deduped) >= limit:
            break
    return deduped


def _looks_definition_like_text(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (value or "")).strip()
    if not cleaned or "?" in cleaned:
        return False
    return bool(MATCHING_DEFINITION_CUE_PATTERN.search(cleaned))


def _normalize_matching_side(value: str, *, max_words: int, min_words: int = 1) -> str | None:
    cleaned = re.sub(r"\s+", " ", (value or "")).strip(" -:;,.")
    if not cleaned:
        return None
    cleaned = _strip_question_prefix(cleaned)
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

    # Reject isolated generic labels (except explicit acronyms like TCP, IPv4).
    if len(tokens) == 1:
        sole = tokens[0].strip()
        sole_norm = content_tokens[0]
        is_acronym = bool(re.fullmatch(r"[A-Z0-9]{2,10}", sole))
        if not is_acronym:
            return True
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
        # Keep full, explicit sentence when cleanup removed too much context.
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
            and lone not in MATCHING_GENERIC_TOKEN_STOPWORDS
        ):
            return False
    if any(len(token.strip("'’-")) <= 1 for token in left_tokens):
        return False
    content_tokens = [
        token
        for token in left_tokens
        if _normalize_identifier(token) not in MATCHING_GENERIC_TOKEN_STOPWORDS
    ]
    if any(_normalize_identifier(token) in MATCHING_LEFT_FORBIDDEN_TOKENS for token in left_tokens):
        return False
    if len(content_tokens) < 2:
        # Accept simple labels such as "Le routeur" or "Conduction" when they
        # are specific and non-generic.
        if not (
            len(content_tokens) == 1
            and len(left_tokens) <= 3
            and len(_normalize_identifier(content_tokens[0])) >= 4
            and _normalize_identifier(content_tokens[0]) not in MATCHING_GENERIC_SINGLE_LABEL_TOKENS
            and _normalize_identifier(content_tokens[0]) not in MATCHING_STOPWORDS
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
    if MATCHING_RIGHT_NOISY_START_PATTERN.match(right_cleaned):
        return False
    if MATCHING_RIGHT_BAD_END_PATTERN.search(right_cleaned):
        return False
    if len(right_cleaned.split()) < MATCHING_RIGHT_MIN_WORDS:
        return False
    if not _looks_definition_like_text(right_cleaned) and len(right_cleaned.split()) < 8:
        return False
    if right_key.startswith(left_key):
        # Allow explicit predicate definitions after the concept label:
        # "Le routeur -> Le routeur oriente les paquets ...".
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
    """Score matching pairs to keep the most pedagogically useful candidates."""

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


def _extract_pairs_from_blob(blob: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if not blob.strip():
        return pairs

    for fragment in re.split(r"\s*(?:\|\||;;|;|\n)+\s*", blob):
        part = fragment.strip()
        if not part:
            continue
        for separator in ("->", "=>", "→", "-&gt;", "="):
            if separator in part:
                left_raw, right_raw = part.split(separator, 1)
                pairs.append((left_raw, right_raw))
                break
        else:
            if ":" in part:
                left_raw, right_raw = part.split(":", 1)
                left_candidate = _normalize_matching_side(
                    _normalize_matching_left_candidate(left_raw),
                    max_words=8,
                    min_words=1,
                )
                if (
                    left_candidate
                    and not MATCHING_LEFT_VERB_PATTERN.search(left_candidate)
                    and "," not in left_raw
                    and "?" not in left_raw
                ):
                    pairs.append((left_raw, right_raw))
                    continue
            if " - " in part:
                left_raw, right_raw = part.split(" - ", 1)
                left_candidate = _normalize_matching_side(
                    _normalize_matching_left_candidate(left_raw),
                    max_words=8,
                    min_words=1,
                )
                if left_candidate and not MATCHING_LEFT_VERB_PATTERN.search(left_candidate):
                    pairs.append((left_raw, right_raw))
    return pairs


def _extract_pairs_from_sentence(sentence: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    candidate = sentence.strip(" -:;,.")
    if not candidate:
        return pairs

    if ":" in candidate:
        left, right = candidate.split(":", 1)
        left_candidate = _normalize_matching_side(
            _normalize_matching_left_candidate(left),
            max_words=8,
            min_words=1,
        )
        if (
            left_candidate
            and right.strip()
            and "," not in left
            and "?" not in left
            and not MATCHING_LEFT_VERB_PATTERN.search(left_candidate)
        ):
            pairs.append((left, right))

    match = MATCHING_SENTENCE_PAIR_PATTERN.search(candidate)
    if match:
        predicate = match.group(2).strip(" ,:-")
        right = f"{predicate} {match.group(3)}".strip(" ,:-")
        if _looks_definition_like_text(right):
            left = _derive_matching_label(match.group(1).strip(" ,:-"))
            if left and right:
                pairs.append((left, right))

    cest_a_dire_match = MATCHING_CEST_A_DIRE_PAIR_PATTERN.search(candidate)
    if cest_a_dire_match:
        left = _derive_matching_label(cest_a_dire_match.group(1).strip(" ,:-"))
        right = cest_a_dire_match.group(2).strip(" ,:-")
        if left and right and _looks_definition_like_text(f"c'est-a-dire {right}"):
            pairs.append((left, right))

    return pairs


def _derive_matching_label(sentence: str) -> str | None:
    sentence_clean = sentence.strip(" -:;,.")
    match = MATCHING_SENTENCE_PAIR_PATTERN.search(sentence_clean)
    if match:
        candidate = match.group(1).strip(" -:;,.")
    else:
        noun_phrase_match = MATCHING_LEADING_NOUN_PHRASE_PATTERN.search(sentence_clean)
        if noun_phrase_match:
            candidate = noun_phrase_match.group(1).strip(" -:;,.")
        else:
            article_phrase_match = MATCHING_LEFT_ARTICLE_PHRASE_PATTERN.search(sentence_clean)
            if article_phrase_match:
                candidate = article_phrase_match.group(1).strip(" -:;,.")
            else:
                # Avoid extracting left labels from arbitrary sentence fragments.
                return None
    if not candidate:
        return None

    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]+", candidate)
    selected: list[str] = []
    for token in tokens:
        normalized = _normalize_identifier(token)
        if len(normalized) < 3:
            continue
        if normalized in MATCHING_GENERIC_TOKEN_STOPWORDS:
            continue
        if normalized in MATCHING_LEFT_FORBIDDEN_TOKENS:
            continue
        if normalized in MATCHING_LABEL_BANNED_TOKENS:
            continue
        selected.append(token)
        if len(selected) >= 3:
            break

    if len(selected) < 2:
        # Fallback: recover a noun phrase if the leading clause starts with
        # discourse noise ("On suppose...", "Toutes les..."), then build a label.
        noun_phrase_match = MATCHING_LEFT_ARTICLE_PHRASE_PATTERN.search(sentence_clean)
        if noun_phrase_match:
            fallback_candidate = noun_phrase_match.group(1).strip(" -:;,.")
            direct_label = _normalize_matching_side(
                _normalize_matching_left_candidate(fallback_candidate),
                max_words=6,
                min_words=1,
            )
            if direct_label and not MATCHING_LEFT_VERB_PATTERN.search(direct_label):
                return direct_label
            fallback_tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9'-]+", fallback_candidate)
            selected = []
            for token in fallback_tokens:
                normalized = _normalize_identifier(token)
                if len(normalized) < 3:
                    continue
                if normalized in MATCHING_GENERIC_TOKEN_STOPWORDS:
                    continue
                if normalized in MATCHING_LEFT_FORBIDDEN_TOKENS:
                    continue
                if normalized in MATCHING_LABEL_BANNED_TOKENS:
                    continue
                selected.append(token)
                if len(selected) >= 3:
                    break
        if len(selected) == 1:
            return None
        if len(selected) < 2:
            return None
    label = _normalize_matching_side(
        _normalize_matching_left_candidate(" ".join(selected)),
        max_words=6,
        min_words=1,
    )
    if not label:
        return None
    if MATCHING_LEFT_VERB_PATTERN.search(label):
        return None
    return label


def _build_matching_fallback_pairs(source_text: str, *, desired_pairs: int = 4) -> list[tuple[str, str]]:
    """Build quality association pairs from full source sentences."""

    sentences = _split_informative_sentences(source_text, minimum_length=28, limit=80)
    candidates: list[tuple[int, str, str, int]] = []
    seen_exact: set[tuple[str, str]] = set()
    sequence = 0

    def add_pair(left_raw: str, right_raw: str) -> None:
        nonlocal sequence
        left = _normalize_matching_side(
            _normalize_matching_left_candidate(left_raw),
            max_words=8,
            min_words=1,
        )
        if not left:
            return
        left = _normalize_matching_left_display(left)
        right = _coerce_matching_definition(left, right_raw)
        if not right:
            return
        if not _is_valid_matching_pair(left, right):
            return
        key = (left.lower(), right.lower())
        if key in seen_exact:
            return
        seen_exact.add(key)
        sequence += 1
        candidates.append((sequence, left, right, _matching_pair_quality_score(left, right)))

    for sentence in sentences:
        for left_raw, right_raw in _extract_pairs_from_sentence(sentence):
            add_pair(left_raw, right_raw)

    used_rights = {right.lower() for _, _, right, _ in candidates}
    for sentence in sentences:
        sentence_key = sentence.lower()
        if sentence_key in used_rights:
            continue
        if not _looks_definition_like_text(sentence):
            continue
        left_raw = _derive_matching_label(sentence)
        if not left_raw:
            continue
        right_raw = sentence
        before_count = len(candidates)
        add_pair(left_raw, right_raw)
        if len(candidates) > before_count:
            used_rights.add(sentence_key)

    selected = _select_best_matching_pairs(candidates, limit=max(2, desired_pairs))

    if len(selected) < 2:
        context = sentences[0] if sentences else "Le document presente des notions importantes."
        add_pair("Concept principal", context)
        add_pair("Cas pratique", "Associer chaque notion a son role explicite dans le texte source.")
        add_pair("Exemple concret", "Relier chaque notion a une illustration concrete du document.")
        selected = _select_best_matching_pairs(candidates, limit=max(2, desired_pairs))

    return selected[: max(2, desired_pairs)]


def _extract_matching_pairs(*, item: GeneratedItem, source_text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[int, str, str, int]] = []
    seen_exact: set[tuple[str, str]] = set()
    sequence = 0

    def add_pair(left_raw: str, right_raw: str) -> None:
        nonlocal sequence
        left = _normalize_matching_side(
            _normalize_matching_left_candidate(left_raw),
            max_words=8,
            min_words=1,
        )
        if not left:
            return
        left = _normalize_matching_left_display(left)
        right = _coerce_matching_definition(left, right_raw)
        if not right:
            return
        if not _is_valid_matching_pair(left, right):
            return
        key = (left.lower(), right.lower())
        if key in seen_exact:
            return
        seen_exact.add(key)
        sequence += 1
        candidates.append((sequence, left, right, _matching_pair_quality_score(left, right)))

    raw_sources = [item.correct_answer or "", *item.answer_options, *item.distractors]
    for candidate in raw_sources:
        for left_raw, right_raw in _extract_pairs_from_blob(candidate):
            add_pair(left_raw, right_raw)

    selected = _select_best_matching_pairs(candidates, limit=8)

    if len(selected) < 3:
        for sentence in _split_informative_sentences(
            _sanitize_source_for_generation(source_text), minimum_length=28, limit=80
        ):
            for left_raw, right_raw in _extract_pairs_from_sentence(sentence):
                add_pair(left_raw, right_raw)
        selected = _select_best_matching_pairs(candidates, limit=8)

    if len(selected) < 2:
        for left_raw, right_raw in _build_matching_fallback_pairs(
            source_text=_sanitize_source_for_generation(source_text),
            desired_pairs=4,
        ):
            add_pair(left_raw, right_raw)
        selected = _select_best_matching_pairs(candidates, limit=8)

    if len(selected) < 2:
        return [
            ("Concept principal", "Definition complete basee sur le texte source."),
            ("Notion cle", "Lien explicite avec le contenu pedagogique fourni."),
            ("Exemple concret", "Illustration precise qui aide a valider la comprehension."),
        ]
    return selected[:8]


def _matching_pairs_need_fallback(pairs: list[tuple[str, str]]) -> bool:
    if len(pairs) < 3:
        return True

    if any(not _is_valid_matching_pair(left, right) for left, right in pairs):
        return True

    unique_left: set[str] = set()
    unique_right: set[str] = set()
    for left, _ in pairs:
        normalized = _normalize_identifier(_strip_matching_leading_articles(left))
        if normalized:
            unique_left.add(normalized)
    for _, right in pairs:
        normalized = _normalize_identifier(right)
        if normalized:
            unique_right.add(normalized)
    if len(unique_left) < 3:
        return True
    if len(unique_left) != len(pairs):
        return True
    if len(unique_right) != len(pairs):
        return True

    average_right_words = sum(len(right.split()) for _, right in pairs) / max(1, len(pairs))
    if average_right_words < max(4, MATCHING_RIGHT_MIN_WORDS):
        return True
    if any(MATCHING_WEAK_DEFINITION_PATTERN.match(right.strip()) for _, right in pairs):
        return True

    return False


def _matching_pairs_are_exportable(pairs: list[tuple[str, str]]) -> bool:
    """Relaxed validation used for Pronote association mode (min 2 strong pairs)."""

    if len(pairs) < 2:
        return False
    if any(not _is_valid_matching_pair(left, right) for left, right in pairs):
        return False

    unique_left: set[str] = set()
    unique_right: set[str] = set()
    for left, _ in pairs:
        normalized = _normalize_identifier(_strip_matching_leading_articles(left))
        if normalized:
            unique_left.add(normalized)
    for _, right in pairs:
        normalized = _normalize_identifier(right)
        if normalized:
            unique_right.add(normalized)

    return len(unique_left) == len(pairs) and len(unique_right) == len(pairs)


def _matching_pairs_are_pronote_ready(pairs: list[tuple[str, str]]) -> bool:
    """Stricter quality gate for Pronote association mode."""

    if not _matching_pairs_are_exportable(pairs):
        return False
    if len(pairs) < 2:
        return False

    right_lengths = [len(right.split()) for _, right in pairs]
    if not right_lengths:
        return False
    if min(right_lengths) < max(4, MATCHING_RIGHT_MIN_WORDS):
        return False
    if (sum(right_lengths) / len(right_lengths)) < 6:
        return False

    for left, right in pairs:
        left_key = _normalize_identifier(_strip_matching_leading_articles(left))
        right_key = _normalize_identifier(right)
        if not left_key or not right_key:
            return False
        if left_key in right_key and len(right.split()) <= len(left.split()) + 2:
            return False
        if MATCHING_WEAK_CERTAINTY_PATTERN.search(right):
            return False

    return True


def _build_association_prompt_from_pairs(pairs: list[tuple[str, str]]) -> str:
    """Create a concise association prompt from the selected notions."""
    return "Associez chaque notion du texte a sa definition ou a sa caracteristique correspondante."
