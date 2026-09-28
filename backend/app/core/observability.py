"""Acceso centralizado a la observabilidad del sistema."""

import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from functools import lru_cache, wraps
from types import TracebackType
from typing import Any
from uuid import UUID

from langfuse import Langfuse
from langfuse.types import TraceContext

from app.core.config import settings

logger = logging.getLogger(__name__)


def observability_enabled() -> bool:
    """Indica si la observabilidad está configurada y habilitada."""

    public_key = (
        settings.langfuse_public_key
        .get_secret_value()
        .strip()
    )
    secret_key = (
        settings.langfuse_secret_key
        .get_secret_value()
        .strip()
    )

    return (
        settings.langfuse_tracing_enabled
        and bool(public_key)
        and bool(secret_key)
    )


def build_trace_context(
    execution_id: str,
) -> TraceContext:
    """Construye el contexto Langfuse usando el ID de ejecución."""

    return {
        "trace_id": UUID(execution_id).hex,
    }


@lru_cache(maxsize=1)
def get_observability_client() -> Langfuse | None:
    """Devuelve el cliente compartido de Langfuse si está habilitado."""

    if not observability_enabled():
        return None

    return Langfuse(
        public_key=(
            settings.langfuse_public_key
            .get_secret_value()
            .strip()
        ),
        secret_key=(
            settings.langfuse_secret_key
            .get_secret_value()
            .strip()
        ),
        base_url=settings.langfuse_base_url.rstrip("/"),
        tracing_enabled=settings.langfuse_tracing_enabled,
    )


class SafeObservationContext:
    """Aísla fallos de observabilidad del flujo funcional."""

    def __init__(
        self,
        context: AbstractContextManager[Any] | None,
    ) -> None:
        self._context = context
        self._observation: Any = None

    def __enter__(self) -> Any:
        if self._context is None:
            return None

        try:
            self._observation = self._context.__enter__()
        except Exception:
            logger.exception(
                "No se pudo entrar al contexto de observabilidad."
            )
            self._context = None
            self._observation = None

        return self._observation

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self._context is None:
            return False

        try:
            self._context.__exit__(
                exc_type,
                exc_value,
                traceback,
            )
        except Exception:
            logger.exception(
                "No se pudo cerrar el contexto de observabilidad."
            )

        return False


def get_current_trace_context() -> TraceContext | None:
    """Obtiene el contexto activo para propagar la traza."""

    try:
        client = get_observability_client()

        if client is None:
            return None

        trace_id = client.get_current_trace_id()
        observation_id = client.get_current_observation_id()

        if not trace_id or not observation_id:
            return None

        return {
            "trace_id": trace_id,
            "parent_span_id": observation_id,
        }
    except Exception:
        logger.exception(
            "No se pudo obtener el contexto activo de observabilidad."
        )
        return None


def observe_agent(
    name: str,
) -> Callable[
    [Callable[..., Awaitable[Any]]],
    Callable[..., Awaitable[Any]],
]:
    """Añade observabilidad a una operación asíncrona de agente."""

    def decorator(
        operation: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        @wraps(operation)
        async def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            with start_agent_observation(
                name
            ) as observation:
                try:
                    result = await operation(
                        *args,
                        **kwargs,
                    )
                except Exception as error:
                    mark_operation_error(
                        observation,
                        error,
                    )
                    raise

                update_operation_observation(
                    observation,
                    status="success",
                )

                return result

        return wrapper

    return decorator


def start_agent_observation(
    name: str,
    *,
    metadata: dict[str, object] | None = None,
) -> SafeObservationContext:
    """Inicia una observación para un agente del sistema."""

    try:
        client = get_observability_client()
        trace_context = get_current_trace_context()

        if client is None or trace_context is None:
            return SafeObservationContext(None)

        context = client.start_as_current_observation(
            trace_context=trace_context,
            name=f"agent:{name}",
            as_type="agent",
            metadata=metadata,
        )

        return SafeObservationContext(context)
    except Exception:
        logger.exception(
            "No se pudo iniciar la observabilidad del agente %s.",
            name,
        )
        return SafeObservationContext(None)


def start_mcp_tool_observation(
    server: str,
    tool: str,
) -> SafeObservationContext:
    """Inicia una observación para una herramienta MCP."""

    try:
        client = get_observability_client()
        trace_context = get_current_trace_context()

        if client is None or trace_context is None:
            return SafeObservationContext(None)

        context = client.start_as_current_observation(
            trace_context=trace_context,
            name=f"mcp-tool:{tool}",
            as_type="tool",
            metadata={
                "mcp_server": server,
                "mcp_tool": tool,
            },
        )

        return SafeObservationContext(context)
    except Exception:
        logger.exception(
            "No se pudo iniciar la observabilidad de la herramienta MCP %s.",
            tool,
        )
        return SafeObservationContext(None)


def update_operation_observation(
    observation: Any,
    *,
    status: str,
) -> None:
    """Registra el estado real de una operación observada."""

    if observation is None:
        return

    try:
        observation.update(
            output={
                "status": status,
            },
        )
    except Exception:
        logger.exception(
            "No se pudo actualizar una observación."
        )


def mark_operation_error(
    observation: Any,
    error: Exception,
) -> None:
    """Registra un error real sin modificar el flujo funcional."""

    if observation is None:
        return

    try:
        observation.update(
            level="ERROR",
            status_message=str(error),
            output={
                "status": "error",
            },
        )
    except Exception:
        logger.exception(
            "No se pudo registrar el error de una observación."
        )


def build_llm_usage_details(
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> dict[str, int] | None:
    """Normaliza el uso real de tokens para Langfuse."""

    usage: dict[str, int] = {}

    if prompt_tokens is not None:
        usage["input"] = prompt_tokens

    if completion_tokens is not None:
        usage["output"] = completion_tokens

    if (
        prompt_tokens is not None
        and completion_tokens is not None
    ):
        usage["total"] = (
            prompt_tokens + completion_tokens
        )

    return usage or None


def start_llm_generation(
    trace_context: TraceContext | None,
    *,
    model: str,
    input_data: object | None = None,
) -> SafeObservationContext:
    """Inicia una generación LLM asociada a la traza activa."""

    if trace_context is None:
        return SafeObservationContext(None)

    try:
        client = get_observability_client()

        if client is None:
            return SafeObservationContext(None)

        kwargs: dict[str, Any] = {
            "trace_context": trace_context,
            "name": "openrouter-generation",
            "as_type": "generation",
            "model": model,
            "model_parameters": {
                "temperature": settings.llm_temperature,
            },
            "metadata": {
                "provider": "openrouter",
            },
        }

        if (
            settings.langfuse_capture_content
            and input_data is not None
        ):
            kwargs["input"] = input_data

        context = client.start_as_current_observation(
            **kwargs
        )

        return SafeObservationContext(context)
    except Exception:
        logger.exception(
            "No se pudo iniciar la observabilidad de la generación LLM."
        )
        return SafeObservationContext(None)


def update_llm_generation(
    observation: Any,
    *,
    model: str,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    cost_usd: float | None = None,
    output_content: str | None = None,
) -> None:
    """Actualiza la generación con datos reales del proveedor."""

    if observation is None:
        return

    try:
        kwargs: dict[str, Any] = {
            "model": model,
        }

        usage_details = build_llm_usage_details(
            prompt_tokens,
            completion_tokens,
        )

        if usage_details is not None:
            kwargs["usage_details"] = usage_details

        if cost_usd is not None:
            kwargs["cost_details"] = {
                "total": cost_usd,
            }

        if (
            settings.langfuse_capture_content
            and output_content is not None
        ):
            kwargs["output"] = output_content

        observation.update(**kwargs)
    except Exception:
        logger.exception(
            "No se pudo actualizar la observabilidad de la generación LLM."
        )


def mark_llm_generation_error(
    observation: Any,
    error: Exception,
) -> None:
    """Registra un fallo real del proveedor sin alterar su propagación."""

    if observation is None:
        return

    try:
        observation.update(
            level="ERROR",
            status_message=str(error),
        )
    except Exception:
        logger.exception(
            "No se pudo registrar el error de la generación LLM."
        )


def start_pipeline_observation(
    execution_id: str,
) -> SafeObservationContext:
    """Inicia la observación raíz del pipeline."""

    try:
        client = get_observability_client()

        if client is None:
            return SafeObservationContext(None)

        context = client.start_as_current_observation(
            trace_context=build_trace_context(
                execution_id
            ),
            name="contract-analysis",
            as_type="chain",
            metadata={
                "execution_id": execution_id,
            },
        )

        return SafeObservationContext(context)
    except Exception:
        logger.exception(
            "No se pudo iniciar la observabilidad del pipeline."
        )
        return SafeObservationContext(None)


def update_pipeline_observation(
    observation: Any,
    *,
    status: str,
    reused_analysis: bool,
    error_count: int,
) -> None:
    """Actualiza la observación sin afectar al pipeline."""

    if observation is None:
        return

    try:
        observation.update(
            output={
                "status": status,
                "reused_analysis": reused_analysis,
                "error_count": error_count,
            },
        )
    except Exception:
        logger.exception(
            "No se pudo actualizar la observabilidad del pipeline."
        )
