from __future__ import annotations

from shared.config import get_settings
import shared.llm.providers as providers


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_get_provider_selects_mistral(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    get_settings.cache_clear()

    provider = providers.get_provider()
    assert isinstance(provider, providers.MistralProvider)

    get_settings.cache_clear()


def test_mistral_provider_parses_chat_completion(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-small-latest")
    monkeypatch.setenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
    get_settings.cache_clear()

    captured: dict = {}

    def fake_post(url: str, *, headers: dict, json: dict, timeout: int):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"items":[{"item_type":"mcq","prompt":"Q1"}],"content_types":["mcq"]}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(providers.httpx, "post", fake_post)

    provider = providers.MistralProvider()
    output = provider.generate("Prompt de test")

    assert output.startswith('{"items"')
    assert captured["url"] == "https://api.mistral.ai/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "mistral-small-latest"
    assert captured["json"]["response_format"] == {"type": "json_object"}

    get_settings.cache_clear()
