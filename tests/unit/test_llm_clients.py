import pytest
from app.llm import (
    model_gateway,
    openrouter_client,
)
from app.llm.models import (
    ChatMessage,
    ModelProviderError,
    ModelResponse,
)
from pydantic import SecretStr


class FakeResponse:
    """Simula una respuesta HTTP válida."""

    def __init__(
        self,
        payload: dict[str, object],
    ) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        """Simula una respuesta sin error HTTP."""

    def json(self) -> dict[str, object]:
        """Devuelve el contenido configurado."""

        return self.payload


def create_messages() -> list[ChatMessage]:
    """Crea mensajes para las pruebas."""

    return [
        ChatMessage(
            role="system",
            content="Analiza la cláusula.",
        ),
        ChatMessage(
            role="user",
            content="El proveedor podrá modificarla.",
        ),
    ]



def test_openrouter_requires_api_key(
    monkeypatch,
) -> None:
    """Controla la ausencia de credenciales."""

    monkeypatch.setattr(
        openrouter_client.settings,
        "openrouter_api_key",
        SecretStr(""),
    )

    with pytest.raises(
        ModelProviderError,
        match="OPENROUTER_API_KEY",
    ):
        openrouter_client.generate_with_openrouter(create_messages())


def test_openrouter_client_generates_response(
    monkeypatch,
) -> None:
    """Comprueba la solicitud remota."""

    monkeypatch.setattr(
        openrouter_client.settings,
        "openrouter_api_key",
        SecretStr("test-key"),
    )
    monkeypatch.setattr(
        openrouter_client.settings,
        "openrouter_model",
        "deepseek/deepseek-v4-flash-0731",
    )

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        assert url.endswith("/chat/completions")
        assert headers["Authorization"] == ("Bearer test-key")
        assert json["model"] == ("deepseek/deepseek-v4-flash-0731")
        assert "response_format" in json
        assert timeout == 120.0

        return FakeResponse(
            {
                "model": ("deepseek/deepseek-v4-flash-0731"),
                "choices": [
                    {
                        "message": {
                            "content": ('{"classification": "potentially_abusive"}')
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 200,
                    "completion_tokens": 50,
                },
            }
        )

    monkeypatch.setattr(
        openrouter_client.httpx,
        "post",
        fake_post,
    )

    result = openrouter_client.generate_with_openrouter(
        create_messages(),
        {"type": "object"},
    )

    assert result.provider == "openrouter"
    assert result.prompt_tokens == 200
    assert result.completion_tokens == 50




def test_gateway_uses_openrouter(
    monkeypatch,
) -> None:
    """Usa OpenRouter como proveedor del Analizador Legal."""

    expected = ModelResponse(
        provider="openrouter",
        model="deepseek/deepseek-v4-flash-0731",
        content='{"classification": "not_potentially_abusive"}',
    )

    monkeypatch.setattr(
        model_gateway,
        "generate_with_openrouter",
        lambda messages, schema: expected,
    )

    result = model_gateway.generate_model_response(
        create_messages()
    )

    assert result == expected
