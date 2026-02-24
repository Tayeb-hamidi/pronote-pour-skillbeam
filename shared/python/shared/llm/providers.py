"""Provider abstractions for text generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
import time

import httpx

from shared.config import get_settings
from shared.enums import ContentType, ItemType

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract language model provider."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from prompt."""


class OpenAIProvider(LLMProvider):
    """OpenAI provider stub.

    TODO: wire with official OpenAI SDK and robust JSON mode.
    """

    def generate(self, prompt: str) -> str:
        settings = get_settings()
        if not settings.openai_api_key:
            return _fallback_json_payload()

        # Stubbed HTTP call to avoid hard dependency and keep provider abstraction in place.
        return _fallback_json_payload()


class MistralProvider(LLMProvider):
    """Mistral API provider via chat completions."""

    def generate(self, prompt: str) -> str:
        settings = get_settings()
        if not settings.mistral_api_key:
            return _fallback_json_payload()

        url = f"{settings.mistral_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.mistral_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.mistral_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "Tu retournes uniquement un JSON valide.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }

        timeout = httpx.Timeout(
            timeout=settings.request_timeout_seconds,
            connect=min(10.0, float(settings.request_timeout_seconds)),
        )
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                text = _extract_chat_completion_content(response.json())
                if text:
                    return text
                last_error = RuntimeError("empty_mistral_response")
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(1.5 * attempt)
                    continue

        if last_error is not None:
            logger.warning(
                "mistral call failed after retries, fallback payload used: %s",
                str(last_error)[:300],
            )
        return _fallback_json_payload()


class LocalVLLMProvider(LLMProvider):
    """Local vLLM provider stub with fallback."""

    def generate(self, prompt: str) -> str:
        settings = get_settings()
        url = f"{settings.local_vllm_base_url.rstrip('/')}/generate"
        try:
            response = httpx.post(url, json={"prompt": prompt}, timeout=8)
            response.raise_for_status()
            data = response.json()
            text = data.get("text") if isinstance(data, dict) else None
            if isinstance(text, str) and text.strip():
                return text
        except Exception:
            pass
        return _fallback_json_payload()


def get_provider() -> LLMProvider:
    """Select provider implementation from env."""

    settings = get_settings()
    if settings.llm_provider == "mistral":
        return MistralProvider()
    if settings.llm_provider == "openai":
        return OpenAIProvider()
    return LocalVLLMProvider()


def _extract_chat_completion_content(payload: dict) -> str | None:
    """Extract text content from chat completion response payload."""

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    message = choices[0].get("message")
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
            elif isinstance(part, str) and part.strip():
                chunks.append(part.strip())
        combined = "\n".join(chunks).strip()
        return combined or None
    return None


def _fallback_json_payload() -> str:
    """Deterministic fallback JSON output for offline development."""

    payload = {
        "items": [
            {
                "item_type": ItemType.MCQ.value,
                "prompt": "Quelle est l'idee principale de la section 1 ?",
                "correct_answer": "L'idee principale est la comprehension du concept central.",
                "distractors": [
                    "Un detail secondaire sans lien",
                    "Une definition historique hors sujet",
                    "Une citation non pertinente",
                ],
                "answer_options": [],
                "tags": ["concept_cle"],
                "difficulty": "medium",
                "feedback": "S'appuyer sur la section source pour justifier la reponse.",
                "source_reference": "section:1",
            }
        ],
        "content_types": [ContentType.MCQ.value],
    }
    return json.dumps(payload, ensure_ascii=True)
