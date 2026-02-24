import re

from shared.enums import ContentType
from shared.generation.templates import generate_items
from shared.llm.providers import LLMProvider


class EmptyProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return "{}"


class CaptureProvider(LLMProvider):
    def __init__(self) -> None:
        self.last_prompt = ""

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return "{}"


class PartiallyValidProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
```json
{
  "items": [
    {
      "type": "multiple_choice",
      "question": "Selon le texte, que provoque la photosynthese ?",
      "answer": "Elle produit du glucose et de l'oxygene.",
      "options": [
        "Elle produit du glucose et de l'oxygene.",
        "Elle consomme tout l'oxygene de l'atmosphere.",
        "Elle n'utilise pas la lumiere.",
        "Elle bloque la croissance des plantes."
      ],
      "difficulty": "medium"
    },
    {
      "item_type": "open_question",
      "prompt": "",
      "correct_answer": "invalide"
    }
  ]
}
```
        """.strip()


class PronoteMismatchProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
{
  "items": [
    {
      "item_type": "open_question",
      "prompt": "Q13. Quel dispositif le candidat a-t-il cofonde pour outiller la differenciation pedagogique ?",
      "correct_answer": "SkillBeam AI-Edu",
      "difficulty": "medium"
    },
    {
      "item_type": "open_question",
      "prompt": "Question 14: completez avec le terme attendu",
      "correct_answer": "autonomie",
      "difficulty": "medium"
    }
  ]
}
        """.strip()


class BrokenMatchingProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
{
  "items": [
    {
      "item_type": "matching",
      "prompt": "Q1. Associez les notions",
      "correct_answer": "Le diagramme temporel -> est le suivant ; On suppose le reseau parfait, c -> est-a-dire sans perte ; Toutes les lettres -> sont arrivees ; Bien entendu -> ajout de ces infos"
    }
  ]
}
        """.strip()


class DuplicateMatchingProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
{
  "items": [
    {
      "item_type": "matching",
      "prompt": "Associez les notions",
      "correct_answer": "Le diagramme temporel -> Le diagramme || Le diagramme temporel -> Le diagramme temporel represente l'ordre des lettres || Le protocole de repetition -> Le protocole de repetition",
      "answer_options": [
        "Le protocole de repetition -> Le protocole de repetition renvoie une trame apres timeout",
        "Le reseau parfait -> sans perte"
      ]
    }
  ]
}
        """.strip()


class SingleWeakAssociationProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
{
  "items": [
    {
      "item_type": "open_question",
      "prompt": "Quelle est l'idee principale du document ?",
      "correct_answer": "Definition de notion",
      "answer_options": ["APPROCHE", "SEAUX", "Comment"]
    }
  ]
}
        """.strip()


class NoisyMatchingProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
{
  "items": [
    {
      "item_type": "matching",
      "prompt": "Associez les notions reseau",
      "correct_answer": "Le diagramme temporel -> est le suivant ; On suppose le reseau parfait, c -> est-a-dire sans perte ; Toutes les lettres -> sont arrivees",
      "answer_options": ["APPROCHE", "SEAUX", "Comment"]
    }
  ]
}
        """.strip()


class AccentedMatchingProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
{
  "items": [
    {
      "item_type": "matching",
      "prompt": "Associez les notions reseau",
      "correct_answer": "Le reseau parfait -> c'est-à-dire sans perte de lettres et avec un temps de traversée constant ; Le diagramme temporel -> est le suivant, on suppose que chaque lettre a été postée un jour différent ; Le protocole de repetition -> permet de relancer une trame manquante"
    }
  ]
}
        """.strip()


class NoisyConversationAssociationProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
{
  "items": [
    {
      "item_type": "matching",
      "prompt": "Associez chaque notion a sa definition",
      "correct_answer": "Paquets pas arriver -> Les paquets ne vont pas arriver car il faut que tous les liens aient le même débit ; Côté chef cuisinier -> Du côté du chef cuisinier, il faut qu'il fasse des photocopies ; Le récepteur si -> fait le récepteur si la lettre 3 se perd"
    }
  ]
}
        """.strip()


class AssociationRefinementProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        if '"pairs"' in prompt:
            return """
{
  "pairs": [
    {
      "left": "Reseau parfait",
      "right": "Le reseau parfait garantit une transmission sans perte et un delai de traversee stable."
    },
    {
      "left": "Protocole de repetition",
      "right": "Le protocole de repetition renvoie une trame quand l'accuse de reception attendu est absent."
    },
    {
      "left": "Recepteur",
      "right": "Le recepteur valide les trames recues et signale explicitement les donnees manquantes."
    }
  ]
}
            """.strip()
        return """
{
  "items": [
    {
      "item_type": "matching",
      "prompt": "Associez chaque notion a sa definition",
      "correct_answer": "Côté chef cuisinier -> Du côté du chef cuisinier, il faut qu'il fasse des photocopies ; Maintenant -> les paquets ne vont pas arriver"
    }
  ]
}
        """.strip()


class GenericAssociationLabelsProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        return """
{
  "items": [
    {
      "item_type": "matching",
      "prompt": "Associez les notions",
      "correct_answer": "Exemple -> Une adresse IPv4 comporte une partie reseau et une partie hote ; Quelques contraintes -> Un reseau doit rester disponible ; Reseau tolerant aux pannes -> Limite l'impact d'une panne et retablit rapidement le service"
    }
  ]
}
        """.strip()


def test_mcq_generation_respects_max_items() -> None:
    items = generate_items(
        provider=EmptyProvider(),
        source_text="Les fractions sont des nombres rationnels. Elles ont numerateur et denominateur.",
        content_types=[ContentType.MCQ],
        instructions=None,
        max_items=7,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 7
    assert all(item.item_type.value == "mcq" for item in items)


def test_generation_sanitizes_youtube_noise_in_prompt_and_items() -> None:
    source_text = (
        "Source YouTube: https://www.youtube.com/watch?v=gM_4wJaCNB4\n"
        "Titre: Claude Opus 4.6 : Pourquoi ce Modele va Changer le R0 ?\n"
        "Chaine: Nerdy Kings\n"
        "Ce modele decrit trois impacts majeurs sur l'enseignement.\n"
        "Identifiant video: gM_4wJaCNB4\n"
        "Transcription indisponible sur cette video.\n"
    )

    provider = CaptureProvider()
    items = generate_items(
        provider=provider,
        source_text=source_text,
        content_types=[ContentType.MCQ],
        instructions=None,
        max_items=2,
        language="fr",
        level="intermediate",
    )

    assert "Source YouTube:" not in provider.last_prompt
    assert "https://" not in provider.last_prompt
    assert "Titre:" not in provider.last_prompt
    assert "Chaine:" not in provider.last_prompt
    assert "Transcription indisponible" not in provider.last_prompt

    for item in items:
        assert "https://" not in item.prompt
        assert "Source YouTube" not in item.prompt
        assert "Titre:" not in item.prompt
        assert "Chaine:" not in item.prompt
        assert not (item.correct_answer and "https://" in item.correct_answer)
        for distractor in item.distractors:
            assert "https://" not in distractor


def test_generation_keeps_valid_llm_items_before_fallback() -> None:
    items = generate_items(
        provider=PartiallyValidProvider(),
        source_text="La photosynthese transforme l'energie lumineuse en energie chimique.",
        content_types=[ContentType.MCQ],
        instructions=None,
        max_items=3,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 3
    assert items[0].prompt.startswith("Selon le texte")
    assert items[0].correct_answer == "Elle produit du glucose et de l'oxygene."
    assert len(items[0].distractors) == 3


def test_pronote_numeric_mode_enforces_numeric_answer_and_clean_prompt() -> None:
    items = generate_items(
        provider=PronoteMismatchProvider(),
        source_text="Le candidat enseigne depuis 2010 et a lance 3 projets pilotes.",
        content_types=[ContentType.OPEN_QUESTION],
        instructions='PRONOTE_MODES_JSON: {"numeric_value": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "open_question"
    assert "numeric_value" in items[0].tags
    assert items[0].correct_answer is not None
    assert items[0].correct_answer.replace(".", "", 1).isdigit()
    assert not items[0].prompt.lower().startswith(("q13", "question 13", "item 13"))


def test_pronote_association_mode_enforces_matching_pairs() -> None:
    items = generate_items(
        provider=PronoteMismatchProvider(),
        source_text="Competence -> capacite; Critere -> indicateur; Evaluation -> evidence.",
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None
    assert "->" in items[0].correct_answer
    assert "association_pairs" in items[0].tags


def test_pronote_association_mode_avoids_placeholder_pairs() -> None:
    items = generate_items(
        provider=PronoteMismatchProvider(),
        source_text=(
            "Un routeur dirige les paquets entre des reseaux differents. "
            "Un commutateur connecte plusieurs equipements au sein d'un reseau local. "
            "Un pare-feu filtre le trafic entrant et sortant selon des regles de securite."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 2

    for pair in pairs:
        assert "->" in pair
        left, right = [part.strip() for part in pair.split("->", 1)]
        assert left
        assert len(right.split()) >= 2
        assert not right.lower().startswith("definition de ")
        assert left.lower() not in {"element a", "element b", "notion a", "notion b"}


def test_pronote_association_mode_rejects_fragment_subjects_and_right_clauses() -> None:
    items = generate_items(
        provider=PronoteMismatchProvider(),
        source_text=(
            "Le diagramme temporel represente l'ordre des transmissions. "
            "On suppose le reseau parfait, c'est-a-dire sans perte de lettres et avec un temps de traversee constant. "
            "Toutes les lettres arrivent au destinataire dans l'ordre d'envoi."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 2
    for pair in pairs:
        assert "->" in pair
        left, right = [part.strip() for part in pair.split("->", 1)]
        assert len(left.split()) >= 2
        assert not left.lower().startswith(("on ", "on suppose", "toutes "))
        assert not right.lower().startswith(("est-a-dire", "c'est-a-dire", "definition de "))


def test_pronote_association_mode_rebuilds_pairs_when_raw_output_is_broken() -> None:
    items = generate_items(
        provider=BrokenMatchingProvider(),
        source_text=(
            "Le diagramme temporel represente l'ordre des transmissions dans le reseau. "
            "Un reseau parfait garantit une transmission sans perte et avec une latence stable. "
            "Le protocole de repetition envoie une nouvelle trame quand un accusé de reception manque. "
            "La detection d'anomalie permet d'isoler rapidement un noeud en defaut."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 3
    for pair in pairs:
        assert "->" in pair
        left, right = [part.strip() for part in pair.split("->", 1)]
        assert len(left.split()) >= 2
        assert not left.lower().startswith(("on ", "bien ", "toutes "))
        assert not left.lower().endswith((" decrit", "décrit", "signifie", "indique", "explique"))
        assert len(right.split()) >= 3
        assert not right.lower().startswith(("est-a-dire", "c'est-a-dire", "definition de "))
        assert "est le suivant" not in right.lower()


def test_pronote_association_mode_prefers_concept_labels_over_predicates() -> None:
    items = generate_items(
        provider=BrokenMatchingProvider(),
        source_text=(
            "Le diagramme temporel décrit l'ordre de transmission des lettres dans le protocole. "
            "Le reseau parfait signifie qu'il n'y a pas de perte et que le temps de traversee est constant. "
            "Le mecanisme d'accuse de reception indique qu'une lettre manquante doit etre renvoyee."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 2

    for pair in pairs:
        left, _right = [part.strip() for part in pair.split("->", 1)]
        assert not left.lower().endswith((" decrit", "décrit", "signifie", "indique", "explique"))


def test_pronote_association_mode_handles_accented_cest_a_dire_fragments() -> None:
    items = generate_items(
        provider=AccentedMatchingProvider(),
        source_text=(
            "Un reseau parfait garantit l'absence de perte de lettres et une latence stable. "
            "Le diagramme temporel represente la chronologie complete d'envoi et de reception. "
            "Le protocole de repetition relance automatiquement une trame quand l'accuse manque."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 2
    for pair in pairs:
        assert "->" in pair
        left, right = [part.strip() for part in pair.split("->", 1)]
        assert len(left.split()) >= 2
        assert len(right.split()) >= 4
        assert "est-à-dire" not in right.lower()
        assert "est le suivant" not in right.lower()


def test_pronote_association_mode_filters_fragment_labels_from_conversational_text() -> None:
    items = generate_items(
        provider=NoisyConversationAssociationProvider(),
        source_text=(
            "Le reseau parfait est une situation sans perte et avec un temps de traversee constant. "
            "Le protocole de repetition permet de renvoyer la lettre manquante en cas d'accuse absent. "
            "Le recepteur confirme la bonne reception et signale les lettres manquantes."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 2
    for pair in pairs:
        left, right = [part.strip() for part in pair.split("->", 1)]
        lowered_left = left.lower()
        assert "pas" not in lowered_left
        assert "cote" not in lowered_left and "côté" not in lowered_left
        assert not lowered_left.endswith(" si")
        assert len(right.split()) >= 4
        assert not right.lower().endswith((" de", " du", " des", " a", " à", " pour"))


def test_pronote_association_mode_uses_llm_refinement_pool_when_available() -> None:
    items = generate_items(
        provider=AssociationRefinementProvider(),
        source_text=(
            "Le reseau parfait est une situation sans perte et avec un temps de traversee constant. "
            "Le protocole de repetition permet de renvoyer la lettre manquante en cas d'accuse absent. "
            "Le recepteur confirme la bonne reception et signale les lettres manquantes."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None
    lowered = items[0].correct_answer.lower()
    assert "protocole de repetition" in lowered
    assert "cote chef cuisinier" not in lowered and "côté chef cuisinier" not in lowered


def test_pronote_association_mode_filters_generic_labels_and_keeps_clean_prompt() -> None:
    items = generate_items(
        provider=GenericAssociationLabelsProvider(),
        source_text=(
            "Le reseau tolerant aux pannes limite l'impact des pannes et restaure rapidement le service. "
            "Une adresse IPv4 identifie un reseau et un hote afin de router correctement les paquets. "
            "Le protocole de repetition relance les trames manquantes apres expiration d'un delai."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None
    assert "(" not in items[0].prompt

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 2
    lowered_pairs = " | ".join(pairs).lower()
    assert "exemple ->" not in lowered_pairs
    assert "quelques contraintes ->" not in lowered_pairs


def test_pronote_multiple_choice_mode_produces_expected_answers() -> None:
    items = generate_items(
        provider=PronoteMismatchProvider(),
        source_text="Differenciation; Feedback; Evaluation formative; Trace ecrite.",
        content_types=[ContentType.MCQ],
        instructions='PRONOTE_MODES_JSON: {"multiple_choice": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "poll"
    assert items[0].correct_answer is not None
    assert items[0].correct_answer.strip() != ""
    assert "multiple_choice" in items[0].tags


def test_pronote_association_mode_removes_duplicate_pairs_and_short_definitions() -> None:
    items = generate_items(
        provider=DuplicateMatchingProvider(),
        source_text=(
            "Le diagramme temporel represente la chronologie complete de transmission des trames. "
            "Le protocole de repetition envoie une nouvelle trame quand l'accuse de reception manque. "
            "Un reseau parfait garantit l'absence de perte et une latence constante."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 1}',
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 2

    left_seen: set[str] = set()
    right_seen: set[str] = set()
    for pair in pairs:
        left, right = [part.strip() for part in pair.split("->", 1)]
        assert len(right.split()) >= 3
        left_key = left.lower()
        right_key = right.lower()
        assert left_key not in left_seen
        assert right_key not in right_seen
        left_seen.add(left_key)
        right_seen.add(right_key)


def test_pronote_association_mode_generates_stable_multi_item_pair_sets() -> None:
    items = generate_items(
        provider=SingleWeakAssociationProvider(),
        source_text=(
            "Le diagramme temporel represente l'ordre de transmission des lettres dans le protocole. "
            "Un reseau parfait garantit une transmission sans perte et avec une latence stable. "
            "Le protocole de repetition envoie une nouvelle trame quand un accuse de reception manque. "
            "La detection d'anomalie permet d'isoler rapidement un noeud en defaut. "
            "La fenetre d'emission limite le nombre de trames envoyees avant acquittement."
        ),
        content_types=[ContentType.MATCHING],
        instructions='PRONOTE_MODES_JSON: {"association_pairs": 3}',
        max_items=3,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 3
    unique_payloads = set()

    for item in items:
        assert item.item_type.value == "matching"
        assert item.correct_answer is not None
        assert item.prompt.lower().startswith("associez")
        pairs = [chunk.strip() for chunk in re.split(r"\|\||;", item.correct_answer) if chunk.strip()]
        assert len(pairs) >= 2
        for pair in pairs:
            assert "->" in pair
            left, right = [part.strip() for part in pair.split("->", 1)]
            assert len(left.split()) >= 2
            assert len(right.split()) >= 5
        unique_payloads.add(item.correct_answer)

    assert len(unique_payloads) >= 2


def test_matching_mode_without_pronote_instructions_still_rebuilds_broken_pairs() -> None:
    items = generate_items(
        provider=NoisyMatchingProvider(),
        source_text=(
            "Le diagramme temporel represente l'ordre de transmission des lettres dans le protocole. "
            "Un reseau parfait garantit une transmission sans perte et avec une latence stable. "
            "Le protocole de repetition envoie une nouvelle trame quand un accuse de reception manque."
        ),
        content_types=[ContentType.MATCHING],
        instructions=None,
        max_items=1,
        language="fr",
        level="intermediate",
    )

    assert len(items) == 1
    assert items[0].item_type.value == "matching"
    assert items[0].correct_answer is not None

    pairs = [chunk.strip() for chunk in re.split(r"\|\||;", items[0].correct_answer) if chunk.strip()]
    assert len(pairs) >= 2
    for pair in pairs:
        assert "->" in pair
        left, right = [part.strip() for part in pair.split("->", 1)]
        assert len(left.split()) >= 2
        assert len(right.split()) >= 5
        assert not left.lower().startswith(("on ", "toutes "))
        assert not right.lower().startswith(("est-a-dire", "c'est-a-dire", "on suppose"))
        assert "est le suivant" not in right.lower()
