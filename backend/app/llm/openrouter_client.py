"""Cliente OpenRouter con control acotado de HTTP 429 y trazabilidad."""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from app.core.config import settings
from app.core.observability import (
    mark_llm_generation_error,
    start_llm_generation,
    update_llm_generation,
)
from app.llm.models import ChatMessage, ModelProviderError, ModelResponse

logger = logging.getLogger(__name__)


class OpenRouterClientError(ModelProviderError):
    """Error HTTP o de transporte; conserva metadatos sin exponer credenciales."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.attempts = attempts


def _retry_after_seconds(raw: str | None) -> float | None:
    """Interpreta Retry-After (segundos o fecha HTTP); no adivina encabezados."""
    if not raw:
        return None
    try:
        seconds = float(raw.strip())
        if math.isfinite(seconds) and seconds >= 0:
            return seconds
    except ValueError:
        pass

    try:
        until = parsedate_to_datetime(raw)
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        return max(0.0, (until - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def _rate_limit_delay(response: httpx.Response, attempt: int) -> float | None:
    """Respeta Retry-After. Si supera el máximo aceptable, no reintenta."""
    max_delay = settings.openrouter_retry_max_delay_seconds
    indicated = _retry_after_seconds(response.headers.get("Retry-After"))
    if indicated is not None:
        return indicated if indicated <= max_delay else None
    return min(
        settings.openrouter_retry_initial_delay_seconds * (2 ** (attempt - 1)),
        max_delay,
    )


def generate_with_openrouter(
    messages: list[ChatMessage],
    response_schema: dict[str, object] | None = None,
    trace_context: dict[str, str] | None = None,
    *,
    model: str | None = None,
) -> ModelResponse:
    """Una inferencia con hasta N intentos ante 429, sin cambiar de modelo."""

    if not messages:
        raise ValueError("Se requiere al menos un mensaje.")

    api_key = settings.openrouter_api_key.get_secret_value().strip()
    if not api_key:
        raise OpenRouterClientError("No se configuró OPENROUTER_API_KEY.")

    if model is not None and not model.strip():
        raise ValueError("El identificador del modelo no puede estar vacío.")
    selected_model = model or settings.openrouter_model

    payload: dict[str, object] = {
        "model": selected_model,
        "messages": [message.model_dump() for message in messages],
        "temperature": settings.llm_temperature,
        "usage": {"include": True},
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
        headers["HTTP-Referer"] = settings.openrouter_site_url

    rate_limit_count = 0
    for attempt in range(1, settings.openrouter_retry_max_attempts + 1):
        # Cada solicitud a OpenRouter tiene su propia generación Langfuse.
        # Un HTTP 429 no se oculta en la traza de una respuesta posterior.
        with start_llm_generation(
            trace_context,
            model=selected_model,
            input_data=payload,
        ) as generation:
            try:
                response = httpx.post(
                    f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=settings.llm_timeout_seconds,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                status = error.response.status_code
                mark_llm_generation_error(generation, error)
                if status == 429:
                    rate_limit_count += 1
                    delay = _rate_limit_delay(error.response, attempt)
                    if (
                        attempt < settings.openrouter_retry_max_attempts
                        and delay is not None
                    ):
                        logger.warning(
                            "OpenRouter 429, modelo=%s, intento=%s/%s, espera=%.2fs",
                            selected_model,
                            attempt,
                            settings.openrouter_retry_max_attempts,
                            delay,
                        )
                    else:
                        reason = (
                            "Retry-After supera el límite de espera configurado"
                            if delay is None else "límite de intentos agotado"
                        )
                        raise OpenRouterClientError(
                            f"OpenRouter HTTP 429 para {selected_model} tras "
                            f"{attempt} intento(s): {reason}.",
                            status_code=429,
                            attempts=attempt,
                        ) from error
                else:
                    raise OpenRouterClientError(
                        f"OpenRouter HTTP {status} para {selected_model}; "
                        "no se reintenta automáticamente.",
                        status_code=status,
                        attempts=attempt,
                    ) from error
            except httpx.HTTPError as error:
                mark_llm_generation_error(generation, error)
                raise OpenRouterClientError(
                    "OpenRouter no pudo generar la respuesta: "
                    f"{error}",
                    attempts=attempt,
                ) from error
            else:
                try:
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                except (IndexError, KeyError, TypeError, ValueError) as error:
                    mark_llm_generation_error(generation, error)
                    raise OpenRouterClientError(
                        "OpenRouter devolvió una respuesta JSON inválida.",
                        attempts=attempt,
                    ) from error

                if not isinstance(content, str) or not content.strip():
                    error = OpenRouterClientError(
                        "OpenRouter devolvió una respuesta vacía.",
                        attempts=attempt,
                    )
                    mark_llm_generation_error(generation, error)
                    raise error

                returned_model = body.get("model", selected_model)
                if not isinstance(returned_model, str):
                    returned_model = selected_model

                usage = body.get("usage", {})
                if not isinstance(usage, dict):
                    usage = {}

                raw_prompt_tokens = usage.get("prompt_tokens")
                raw_completion_tokens = usage.get("completion_tokens")
                raw_cost = usage.get("cost")
                prompt_tokens = (
                    raw_prompt_tokens
                    if isinstance(raw_prompt_tokens, int)
                    and not isinstance(raw_prompt_tokens, bool)
                    else None
                )
                completion_tokens = (
                    raw_completion_tokens
                    if isinstance(raw_completion_tokens, int)
                    and not isinstance(raw_completion_tokens, bool)
                    else None
                )
                cost_usd = (
                    float(raw_cost)
                    if isinstance(raw_cost, (int, float))
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
                    request_attempts=attempt,
                    http_429_count=rate_limit_count,
                )

        # La espera es fuera de la observación individual, para no atribuir
        # el backoff a la latencia de inferencia del proveedor.
        time.sleep(delay)

    raise AssertionError("Bucle de reintentos terminó inesperadamente.")
