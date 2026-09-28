import pytest
from pydantic import SecretStr

from app.llm import (
    model_gateway,
    openrouter_client,
)
from app.llm.models import (
    ChatMessage,
    ModelProviderError,
    ModelResponse,
)


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
        assert json["usage"] == {"include": True}
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


def test_openrouter_updates_llm_generation_with_real_usage(
    monkeypatch,
) -> None:
    """Actualiza Langfuse con uso y costo reales de OpenRouter."""

    monkeypatch.setattr(
        openrouter_client.settings,
        "openrouter_api_key",
        SecretStr("test-key"),
    )
    monkeypatch.setattr(
        openrouter_client.settings,
        "openrouter_model",
        "requested-model",
    )

    observation = object()
    started: dict[str, object] = {}
    updated: dict[str, object] = {}

    class FakeGenerationContext:
        def __enter__(self) -> object:
            return observation

        def __exit__(
            self,
            exc_type: object,
            exc_value: object,
            traceback: object,
        ) -> None:
            return None

    def fake_start_llm_generation(
        trace_context: dict[str, str] | None,
        *,
        model: str,
        input_data: object | None = None,
    ) -> FakeGenerationContext:
        started.update(
            {
                "trace_context": trace_context,
                "model": model,
                "input_data": input_data,
            }
        )
        return FakeGenerationContext()

    def fake_update_llm_generation(
        received_observation: object,
        *,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        cost_usd: float | None = None,
        output_content: str | None = None,
    ) -> None:
        updated.update(
            {
                "observation": received_observation,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost_usd,
                "output_content": output_content,
            }
        )

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        return FakeResponse(
            {
                "model": "returned-model",
                "choices": [
                    {
                        "message": {
                            "content": '{"classification": "potentially_abusive"}'
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 321,
                    "completion_tokens": 87,
                    "cost": 0.0042,
                },
            }
        )

    monkeypatch.setattr(
        openrouter_client,
        "start_llm_generation",
        fake_start_llm_generation,
    )
    monkeypatch.setattr(
        openrouter_client,
        "update_llm_generation",
        fake_update_llm_generation,
    )
    monkeypatch.setattr(
        openrouter_client.httpx,
        "post",
        fake_post,
    )

    trace_context = {
        "trace_id": "a" * 32,
        "parent_span_id": "b" * 16,
    }

    result = openrouter_client.generate_with_openrouter(
        create_messages(),
        trace_context=trace_context,
    )

    assert started["trace_context"] == trace_context
    assert started["model"] == "requested-model"

    assert updated == {
        "observation": observation,
        "model": "returned-model",
        "prompt_tokens": 321,
        "completion_tokens": 87,
        "cost_usd": 0.0042,
        "output_content": '{"classification": "potentially_abusive"}',
    }

    assert result.model == "returned-model"
    assert result.prompt_tokens == 321
    assert result.completion_tokens == 87
    assert result.cost_usd == 0.0042

def test_openrouter_marks_llm_generation_error(
    monkeypatch,
) -> None:
    """Marca la generación cuando OpenRouter falla."""

    monkeypatch.setattr(
        openrouter_client.settings,
        "openrouter_api_key",
        SecretStr("test-key"),
    )

    observation = object()
    captured: dict[str, object] = {}

    class FakeGenerationContext:
        def __enter__(self) -> object:
            return observation

        def __exit__(
            self,
            exc_type: object,
            exc_value: object,
            traceback: object,
        ) -> None:
            return None

    monkeypatch.setattr(
        openrouter_client,
        "start_llm_generation",
        lambda *args, **kwargs: FakeGenerationContext(),
    )

    def fake_mark_error(
        received_observation: object,
        error: Exception,
    ) -> None:
        captured["observation"] = received_observation
        captured["error"] = error

    monkeypatch.setattr(
        openrouter_client,
        "mark_llm_generation_error",
        fake_mark_error,
    )

    def fake_post(
        *_args: object,
        **_kwargs: object,
    ) -> FakeResponse:
        raise openrouter_client.httpx.ConnectError(
            "connection failed"
        )

    monkeypatch.setattr(
        openrouter_client.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        ModelProviderError,
        match="OpenRouter no pudo generar",
    ):
        openrouter_client.generate_with_openrouter(
            create_messages(),
            trace_context={
                "trace_id": "a" * 32,
                "parent_span_id": "b" * 16,
            },
        )

    assert captured["observation"] is observation
    assert isinstance(
        captured["error"],
        openrouter_client.httpx.ConnectError,
    )
