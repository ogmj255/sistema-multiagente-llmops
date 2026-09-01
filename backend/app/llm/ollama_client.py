import httpx

from app.core.config import settings
from app.llm.models import (
    ChatMessage,
    ModelProviderError,
    ModelResponse,
)


class OllamaClientError(ModelProviderError):
    """Indica un error controlado de Ollama."""


def generate_with_ollama(
    messages: list[ChatMessage],
    response_schema: dict[str, object] | None = None,
) -> ModelResponse:
    """Genera una respuesta mediante Ollama."""

    if not messages:
        raise ValueError(
            "Se requiere al menos un mensaje."
        )

    payload: dict[str, object] = {
        "model": settings.ollama_model,
        "messages": [
            message.model_dump()
            for message in messages
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": settings.llm_temperature,
        },
    }

    if response_schema is not None:
        payload["format"] = response_schema

    try:
        response = httpx.post(
            (
                f"{settings.ollama_base_url.rstrip('/')}"
                "/api/chat"
            ),
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        content = body["message"]["content"]
    except (
        httpx.HTTPError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise OllamaClientError(
            f"Ollama no pudo generar la respuesta: {error}"
        ) from error

    if not isinstance(content, str) or not content.strip():
        raise OllamaClientError(
            "Ollama devolvió una respuesta vacía."
        )

    prompt_tokens = body.get("prompt_eval_count")
    completion_tokens = body.get("eval_count")

    return ModelResponse(
        provider="ollama",
        model=settings.ollama_model,
        content=content,
        prompt_tokens=(
            prompt_tokens
            if isinstance(prompt_tokens, int)
            else None
        ),
        completion_tokens=(
            completion_tokens
            if isinstance(completion_tokens, int)
            else None
        ),
    )