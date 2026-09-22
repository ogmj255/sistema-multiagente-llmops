from app.llm.models import (
    ChatMessage,
    ModelResponse,
)
from app.llm.openrouter_client import (
    generate_with_openrouter,
)


def generate_model_response(
    messages: list[ChatMessage],
    response_schema: dict[str, object] | None = None,
) -> ModelResponse:
    """Genera la respuesta del Analizador Legal mediante OpenRouter."""

    return generate_with_openrouter(
        messages,
        response_schema,
    )
