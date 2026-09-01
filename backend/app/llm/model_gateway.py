from app.core.config import settings
from app.llm.models import (
    ChatMessage,
    ModelProviderError,
    ModelResponse,
)
from app.llm.ollama_client import (
    generate_with_ollama,
)
from app.llm.openrouter_client import (
    generate_with_openrouter,
)


def generate_model_response(
    messages: list[ChatMessage],
    response_schema: dict[str, object] | None = None,
) -> ModelResponse:
    """Selecciona el proveedor configurado."""

    mode = settings.legal_analyzer_mode

    if mode == "local":
        return generate_with_ollama(
            messages,
            response_schema,
        )

    if mode == "remote":
        return generate_with_openrouter(
            messages,
            response_schema,
        )

    try:
        return generate_with_openrouter(
            messages,
            response_schema,
        )
    except ModelProviderError:
        local_response = generate_with_ollama(
            messages,
            response_schema,
        )

        return local_response.model_copy(
            update={"fallback_used": True}
        )