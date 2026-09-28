import httpx

from app.core.config import settings
from app.core.observability import (
    mark_llm_generation_error,
    start_llm_generation,
    update_llm_generation,
)
from app.llm.models import (
    ChatMessage,
    ModelProviderError,
    ModelResponse,
)


class OpenRouterClientError(ModelProviderError):
    """Indica un error controlado de OpenRouter."""


def generate_with_openrouter(
    messages: list[ChatMessage],
    response_schema: dict[str, object] | None = None,
    trace_context: dict[str, str] | None = None,
) -> ModelResponse:
    """Genera una respuesta mediante OpenRouter."""

    if not messages:
        raise ValueError(
            "Se requiere al menos un mensaje."
        )

    api_key = (
        settings.openrouter_api_key
        .get_secret_value()
        .strip()
    )

    if not api_key:
        raise OpenRouterClientError(
            "No se configuró OPENROUTER_API_KEY."
        )

    payload: dict[str, object] = {
        "model": settings.openrouter_model,
        "messages": [
            message.model_dump()
            for message in messages
        ],
        "temperature": settings.llm_temperature,
        "usage": {
            "include": True,
        },
    }

    if response_schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_response",
                "strict": True,
                "schema": response_schema,
            },
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": settings.openrouter_app_name,
    }

    if settings.openrouter_site_url.strip():
        headers["HTTP-Referer"] = (
            settings.openrouter_site_url
        )

    with start_llm_generation(
        trace_context,
        model=settings.openrouter_model,
        input_data=payload,
    ) as generation:
        try:
            response = httpx.post(
                (
                    f"{settings.openrouter_base_url.rstrip('/')}"
                    "/chat/completions"
                ),
                json=payload,
                headers=headers,
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"][
                "content"
            ]
        except (
            httpx.HTTPError,
            IndexError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            mark_llm_generation_error(
                generation,
                error,
            )
            raise OpenRouterClientError(
                "OpenRouter no pudo generar la respuesta: "
                f"{error}"
            ) from error

        if (
            not isinstance(content, str)
            or not content.strip()
        ):
            error = OpenRouterClientError(
                "OpenRouter devolvió una respuesta vacía."
            )
            mark_llm_generation_error(
                generation,
                error,
            )
            raise error

        returned_model = body.get(
            "model",
            settings.openrouter_model,
        )

        if not isinstance(returned_model, str):
            returned_model = settings.openrouter_model

        usage = body.get("usage", {})

        if not isinstance(usage, dict):
            usage = {}

        raw_prompt_tokens = usage.get(
            "prompt_tokens"
        )
        raw_completion_tokens = usage.get(
            "completion_tokens"
        )
        raw_cost = usage.get("cost")

        prompt_tokens = (
            raw_prompt_tokens
            if isinstance(raw_prompt_tokens, int)
            else None
        )
        completion_tokens = (
            raw_completion_tokens
            if isinstance(
                raw_completion_tokens,
                int,
            )
            else None
        )
        cost_usd = (
            float(raw_cost)
            if isinstance(
                raw_cost,
                (int, float),
            )
            and not isinstance(raw_cost, bool)
            else None
        )

        update_llm_generation(
            generation,
            model=returned_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            output_content=content,
        )

    return ModelResponse(
        provider="openrouter",
        model=returned_model,
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
    )
