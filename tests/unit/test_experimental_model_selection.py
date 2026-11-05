"""El selector experimental no modifica la configuración global del modelo."""

from contextlib import nullcontext

from pydantic import SecretStr

from app.llm import openrouter_client
from app.llm.models import ChatMessage


class StubResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "model": "mistralai/mistral-large-2512",
            "choices": [{"message": {"content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }


def test_override_is_used_without_changing_default_model(monkeypatch):
    monkeypatch.setattr(
        openrouter_client.settings,
        "openrouter_api_key",
        SecretStr("only-a-test-token"),
    )
    monkeypatch.setattr(
        openrouter_client.settings,
        "openrouter_model",
        "deepseek/deepseek-v4-flash-0731",
    )
    monkeypatch.setattr(
        openrouter_client, "start_llm_generation",
        lambda *_args, **_kwargs: nullcontext(None),
    )
    monkeypatch.setattr(
        openrouter_client, "update_llm_generation",
        lambda *_args, **_kwargs: None,
    )
    captured = {}

    def fake_post(url, *, json, headers, timeout):
        captured.update(json)
        assert "only-a-test-token" in headers["Authorization"]
        return StubResponse()

    monkeypatch.setattr(
        openrouter_client.httpx, "post", fake_post,
    )
    result = openrouter_client.generate_with_openrouter(
        [
            ChatMessage(role="user", content="Analiza."),
        ],
        model="mistralai/mistral-large-2512",
    )
    assert captured["model"] == "mistralai/mistral-large-2512"
    assert result.model == "mistralai/mistral-large-2512"
    assert (
        openrouter_client.settings.openrouter_model
        == "deepseek/deepseek-v4-flash-0731"
    )
