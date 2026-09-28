import asyncio

import pytest
from pydantic import SecretStr

from app.core import observability


def clear_observability_cache() -> None:
    """Limpia el cliente compartido entre pruebas."""

    observability.get_observability_client.cache_clear()


def test_observability_enabled_with_credentials(
    monkeypatch,
) -> None:
    """Habilita observabilidad cuando existen credenciales."""

    monkeypatch.setattr(
        observability.settings,
        "langfuse_public_key",
        SecretStr("public-key"),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_secret_key",
        SecretStr("secret-key"),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_tracing_enabled",
        True,
    )

    assert observability.observability_enabled() is True


def test_observability_disabled_without_credentials(
    monkeypatch,
) -> None:
    """Deshabilita observabilidad cuando faltan credenciales."""

    monkeypatch.setattr(
        observability.settings,
        "langfuse_public_key",
        SecretStr(""),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_secret_key",
        SecretStr(""),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_tracing_enabled",
        True,
    )

    assert observability.observability_enabled() is False


def test_observability_disabled_when_tracing_is_disabled(
    monkeypatch,
) -> None:
    """Respeta la desactivación explícita del tracing."""

    monkeypatch.setattr(
        observability.settings,
        "langfuse_public_key",
        SecretStr("public-key"),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_secret_key",
        SecretStr("secret-key"),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_tracing_enabled",
        False,
    )

    assert observability.observability_enabled() is False


def test_observability_client_is_none_when_disabled(
    monkeypatch,
) -> None:
    """No crea un cliente si observabilidad está deshabilitada."""

    clear_observability_cache()

    monkeypatch.setattr(
        observability.settings,
        "langfuse_public_key",
        SecretStr(""),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_secret_key",
        SecretStr(""),
    )

    result = observability.get_observability_client()

    assert result is None

    clear_observability_cache()


def test_observability_client_uses_settings(
    monkeypatch,
) -> None:
    """Construye Langfuse con la configuración de la aplicación."""

    clear_observability_cache()

    expected_client = object()
    captured: dict[str, object] = {}

    def fake_langfuse(**kwargs):
        captured.update(kwargs)
        return expected_client

    monkeypatch.setattr(
        observability.settings,
        "langfuse_public_key",
        SecretStr("public-key"),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_secret_key",
        SecretStr("secret-key"),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_base_url",
        "https://us.cloud.langfuse.com",
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_tracing_enabled",
        True,
    )
    monkeypatch.setattr(
        observability,
        "Langfuse",
        fake_langfuse,
    )

    result = observability.get_observability_client()

    assert result is expected_client
    assert captured == {
        "public_key": "public-key",
        "secret_key": "secret-key",
        "base_url": "https://us.cloud.langfuse.com",
        "tracing_enabled": True,
    }

    clear_observability_cache()

def test_build_trace_context_uses_execution_uuid() -> None:
    """Reutiliza execution_id como identificador de traza."""

    execution_id = (
        "550e8400-e29b-41d4-a716-446655440000"
    )

    result = observability.build_trace_context(
        execution_id
    )

    assert result == {
        "trace_id": (
            "550e8400e29b41d4a716446655440000"
        )
    }



def test_start_pipeline_observation_disabled(
    monkeypatch,
) -> None:
    """Usa un contexto neutro si observabilidad está deshabilitada."""

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: None,
    )

    context = observability.start_pipeline_observation(
        "550e8400-e29b-41d4-a716-446655440000"
    )

    with context as observation:
        assert observation is None


def test_start_pipeline_observation_uses_execution_id(
    monkeypatch,
) -> None:
    """Crea la observación raíz con el ID real de ejecución."""

    captured: dict[str, object] = {}
    expected_observation = object()

    class FakeContext:
        def __enter__(self):
            return expected_observation

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

    class FakeClient:
        def start_as_current_observation(
            self,
            **kwargs,
        ):
            captured.update(kwargs)
            return FakeContext()

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: FakeClient(),
    )

    execution_id = (
        "550e8400-e29b-41d4-a716-446655440000"
    )

    context = observability.start_pipeline_observation(
        execution_id
    )

    with context as observation:
        assert observation is expected_observation

    assert captured == {
        "trace_context": {
            "trace_id": (
                "550e8400e29b41d4a716446655440000"
            ),
        },
        "name": "contract-analysis",
        "as_type": "chain",
        "metadata": {
            "execution_id": execution_id,
        },
    }


def test_start_pipeline_observation_tolerates_failure(
    monkeypatch,
) -> None:
    """No interrumpe el pipeline si Langfuse falla al iniciar."""

    class FakeClient:
        def start_as_current_observation(
            self,
            **kwargs,
        ):
            raise RuntimeError("Langfuse unavailable")

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: FakeClient(),
    )

    context = observability.start_pipeline_observation(
        "550e8400-e29b-41d4-a716-446655440000"
    )

    with context as observation:
        assert observation is None


def test_update_pipeline_observation_uses_real_result() -> None:
    """Actualiza la observación con el resultado recibido."""

    captured: dict[str, object] = {}

    class FakeObservation:
        def update(
            self,
            **kwargs,
        ) -> None:
            captured.update(kwargs)

    observability.update_pipeline_observation(
        FakeObservation(),
        status="partial",
        reused_analysis=False,
        error_count=2,
    )

    assert captured == {
        "output": {
            "status": "partial",
            "reused_analysis": False,
            "error_count": 2,
        },
    }


def test_update_pipeline_observation_tolerates_failure() -> None:
    """No interrumpe el pipeline si Langfuse falla al actualizar."""

    class FakeObservation:
        def update(
            self,
            **kwargs,
        ) -> None:
            raise RuntimeError("Langfuse unavailable")

    observability.update_pipeline_observation(
        FakeObservation(),
        status="success",
        reused_analysis=False,
        error_count=0,
    )


def test_get_current_trace_context_returns_active_context(
    monkeypatch,
) -> None:
    """Devuelve el contexto activo de la observación actual."""

    class FakeClient:
        def get_current_trace_id(self) -> str:
            return "a" * 32

        def get_current_observation_id(self) -> str:
            return "b" * 16

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: FakeClient(),
    )

    result = observability.get_current_trace_context()

    assert result == {
        "trace_id": "a" * 32,
        "parent_span_id": "b" * 16,
    }


def test_get_current_trace_context_returns_none_without_active_ids(
    monkeypatch,
) -> None:
    """No propaga contexto si no existe observación activa."""

    class FakeClient:
        def get_current_trace_id(self):
            return None

        def get_current_observation_id(self):
            return None

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: FakeClient(),
    )

    assert observability.get_current_trace_context() is None


def test_get_current_trace_context_tolerates_failure(
    monkeypatch,
) -> None:
    """No interrumpe el sistema si falla la consulta del contexto."""

    class FakeClient:
        def get_current_trace_id(self):
            raise RuntimeError("Langfuse unavailable")

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: FakeClient(),
    )

    assert observability.get_current_trace_context() is None


def test_build_llm_usage_details_with_complete_usage() -> None:
    """Construye el uso total a partir de tokens reales."""

    result = observability.build_llm_usage_details(
        prompt_tokens=200,
        completion_tokens=50,
    )

    assert result == {
        "input": 200,
        "output": 50,
        "total": 250,
    }


def test_build_llm_usage_details_does_not_invent_total() -> None:
    """No calcula total cuando falta uno de sus componentes."""

    result = observability.build_llm_usage_details(
        prompt_tokens=200,
        completion_tokens=None,
    )

    assert result == {
        "input": 200,
    }


def test_start_llm_generation_hides_content_by_default(
    monkeypatch,
) -> None:
    """No envía contenido cuando su captura está deshabilitada."""

    captured: dict[str, object] = {}
    expected_observation = object()

    class FakeContext:
        def __enter__(self):
            return expected_observation

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

    class FakeClient:
        def start_as_current_observation(
            self,
            **kwargs,
        ):
            captured.update(kwargs)
            return FakeContext()

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        observability.settings,
        "langfuse_capture_content",
        False,
    )
    monkeypatch.setattr(
        observability.settings,
        "llm_temperature",
        0.0,
    )

    context = observability.start_llm_generation(
        {
            "trace_id": "a" * 32,
            "parent_span_id": "b" * 16,
        },
        model="test-model",
        input_data={"messages": ["contenido privado"]},
    )

    with context as observation:
        assert observation is expected_observation

    assert captured["name"] == "openrouter-generation"
    assert captured["as_type"] == "generation"
    assert captured["model"] == "test-model"
    assert captured["metadata"] == {
        "provider": "openrouter",
    }
    assert captured["model_parameters"] == {
        "temperature": 0.0,
    }
    assert "input" not in captured


def test_update_llm_generation_uses_provider_usage(
    monkeypatch,
) -> None:
    """Registra únicamente tokens recibidos del proveedor."""

    captured: dict[str, object] = {}

    class FakeObservation:
        def update(
            self,
            **kwargs,
        ) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        observability.settings,
        "langfuse_capture_content",
        False,
    )

    observability.update_llm_generation(
        FakeObservation(),
        model="returned-model",
        prompt_tokens=3200,
        completion_tokens=450,
        output_content="respuesta privada",
    )

    assert captured == {
        "model": "returned-model",
        "usage_details": {
            "input": 3200,
            "output": 450,
            "total": 3650,
        },
    }


def test_llm_content_can_be_captured_explicitly(
    monkeypatch,
) -> None:
    """Permite contenido solo cuando está habilitado explícitamente."""

    captured: dict[str, object] = {}

    class FakeObservation:
        def update(
            self,
            **kwargs,
        ) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        observability.settings,
        "langfuse_capture_content",
        True,
    )

    observability.update_llm_generation(
        FakeObservation(),
        model="returned-model",
        prompt_tokens=10,
        completion_tokens=5,
        output_content="respuesta real",
    )

    assert captured["output"] == "respuesta real"


def test_mark_llm_generation_error_uses_real_error() -> None:
    """Registra el error recibido sin reemplazarlo por uno ficticio."""

    captured: dict[str, object] = {}

    class FakeObservation:
        def update(
            self,
            **kwargs,
        ) -> None:
            captured.update(kwargs)

    error = RuntimeError("Proveedor no disponible")

    observability.mark_llm_generation_error(
        FakeObservation(),
        error,
    )

    assert captured == {
        "level": "ERROR",
        "status_message": "Proveedor no disponible",
    }


def test_start_agent_observation_uses_agent_type(
    monkeypatch,
) -> None:
    """Crea una observación Langfuse de tipo agent."""

    captured: dict[str, object] = {}
    expected_observation = object()

    class FakeContext:
        def __enter__(self):
            return expected_observation

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

    class FakeClient:
        def start_as_current_observation(
            self,
            **kwargs,
        ):
            captured.update(kwargs)
            return FakeContext()

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        observability,
        "get_current_trace_context",
        lambda: {
            "trace_id": "a" * 32,
            "parent_span_id": "b" * 16,
        },
    )

    context = observability.start_agent_observation(
        "web-scraper",
        metadata={
            "agent": "web-scraper",
        },
    )

    with context as observation:
        assert observation is expected_observation

    assert captured == {
        "trace_context": {
            "trace_id": "a" * 32,
            "parent_span_id": "b" * 16,
        },
        "name": "agent:web-scraper",
        "as_type": "agent",
        "metadata": {
            "agent": "web-scraper",
        },
    }


def test_start_mcp_tool_observation_uses_tool_type(
    monkeypatch,
) -> None:
    """Crea una observación Langfuse de tipo tool."""

    captured: dict[str, object] = {}
    expected_observation = object()

    class FakeContext:
        def __enter__(self):
            return expected_observation

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

    class FakeClient:
        def start_as_current_observation(
            self,
            **kwargs,
        ):
            captured.update(kwargs)
            return FakeContext()

    monkeypatch.setattr(
        observability,
        "get_observability_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        observability,
        "get_current_trace_context",
        lambda: {
            "trace_id": "a" * 32,
            "parent_span_id": "b" * 16,
        },
    )

    context = observability.start_mcp_tool_observation(
        "Agente Web Scraper",
        "extract_terms",
    )

    with context as observation:
        assert observation is expected_observation

    assert captured == {
        "trace_context": {
            "trace_id": "a" * 32,
            "parent_span_id": "b" * 16,
        },
        "name": "mcp-tool:extract_terms",
        "as_type": "tool",
        "metadata": {
            "mcp_server": "Agente Web Scraper",
            "mcp_tool": "extract_terms",
        },
    }


def test_update_operation_observation_records_status() -> None:
    """Registra el estado real de la operación."""

    captured: dict[str, object] = {}

    class FakeObservation:
        def update(
            self,
            **kwargs,
        ) -> None:
            captured.update(kwargs)

    observability.update_operation_observation(
        FakeObservation(),
        status="success",
    )

    assert captured == {
        "output": {
            "status": "success",
        },
    }


def test_mark_operation_error_records_real_error() -> None:
    """Registra el error recibido por la operación."""

    captured: dict[str, object] = {}

    class FakeObservation:
        def update(
            self,
            **kwargs,
        ) -> None:
            captured.update(kwargs)

    error = RuntimeError("fallo MCP real")

    observability.mark_operation_error(
        FakeObservation(),
        error,
    )

    assert captured == {
        "level": "ERROR",
        "status_message": "fallo MCP real",
        "output": {
            "status": "error",
        },
    }



def test_observe_agent_records_success(
    monkeypatch,
) -> None:
    """Marca como exitosa una ejecución real del agente observado."""

    observation = object()
    started: dict[str, object] = {}
    updated: dict[str, object] = {}

    class FakeContext:
        def __enter__(self) -> object:
            return observation

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

    def fake_start(
        name: str,
    ) -> FakeContext:
        started["name"] = name
        return FakeContext()

    def fake_update(
        received_observation: object,
        *,
        status: str,
    ) -> None:
        updated.update(
            {
                "observation": received_observation,
                "status": status,
            }
        )

    monkeypatch.setattr(
        observability,
        "start_agent_observation",
        fake_start,
    )
    monkeypatch.setattr(
        observability,
        "update_operation_observation",
        fake_update,
    )

    @observability.observe_agent("test-agent")
    async def operation() -> str:
        return "resultado"

    result = asyncio.run(operation())

    assert result == "resultado"
    assert started == {
        "name": "test-agent",
    }
    assert updated == {
        "observation": observation,
        "status": "success",
    }


def test_observe_agent_records_real_error(
    monkeypatch,
) -> None:
    """Registra la excepción real de un agente observado."""

    observation = object()
    captured: dict[str, object] = {}

    class FakeContext:
        def __enter__(self) -> object:
            return observation

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

    monkeypatch.setattr(
        observability,
        "start_agent_observation",
        lambda _name: FakeContext(),
    )

    def fake_mark_error(
        received_observation: object,
        error: Exception,
    ) -> None:
        captured["observation"] = received_observation
        captured["error"] = error

    monkeypatch.setattr(
        observability,
        "mark_operation_error",
        fake_mark_error,
    )

    @observability.observe_agent("test-agent")
    async def operation() -> None:
        raise RuntimeError("fallo real del agente")

    with pytest.raises(
        RuntimeError,
        match="fallo real del agente",
    ):
        asyncio.run(operation())

    assert captured["observation"] is observation
    assert isinstance(
        captured["error"],
        RuntimeError,
    )
    assert str(captured["error"]) == (
        "fallo real del agente"
    )



def test_update_llm_generation_uses_provider_cost_only_when_available(
    monkeypatch,
) -> None:
    """Registra solo el costo real recibido del proveedor."""

    calls: list[dict[str, object]] = []

    class FakeObservation:
        def update(
            self,
            **kwargs,
        ) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(
        observability.settings,
        "langfuse_capture_content",
        False,
    )

    observation = FakeObservation()

    observability.update_llm_generation(
        observation,
        model="returned-model",
        prompt_tokens=100,
        completion_tokens=20,
        cost_usd=0.0042,
    )

    observability.update_llm_generation(
        observation,
        model="returned-model",
        prompt_tokens=100,
        completion_tokens=20,
        cost_usd=None,
    )

    assert calls[0]["cost_details"] == {
        "total": 0.0042,
    }
    assert "cost_details" not in calls[1]
