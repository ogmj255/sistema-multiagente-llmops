from app.mcp import observability_tools
from app.schemas.observability import LLMInvocationMetrics


def test_build_execution_observability_tool() -> None:
    """Consolida métricas reales mediante la herramienta MCP."""

    result = observability_tools.build_execution_observability(
        status="partial",
        duration_ms=1500.5,
        llm_metrics=[
            LLMInvocationMetrics(
                provider="openrouter",
                model="model-a",
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
                cost_usd=0.002,
            ),
            LLMInvocationMetrics(
                provider="openrouter",
                model="model-b",
                prompt_tokens=200,
                completion_tokens=40,
                total_tokens=240,
                cost_usd=0.003,
            ),
        ],
        error_count=2,
    )

    assert result["status"] == "partial"
    assert result["duration_ms"] == 1500.5
    assert result["prompt_tokens"] == 300
    assert result["completion_tokens"] == 60
    assert result["total_tokens"] == 360
    assert result["cost_usd"] == 0.005
    assert result["error_count"] == 2
    assert result["llm_invocation_count"] == 2


def test_build_execution_observability_without_reported_cost() -> None:
    """No inventa costo cuando el proveedor no lo reporta."""

    result = observability_tools.build_execution_observability(
        status="success",
        duration_ms=500.0,
        llm_metrics=[
            LLMInvocationMetrics(
                provider="openrouter",
                model="model-test",
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
                cost_usd=None,
            )
        ],
        error_count=0,
    )

    assert result["status"] == "success"
    assert result["total_tokens"] == 120
    assert result["cost_usd"] is None
    assert result["error_count"] == 0
    assert result["llm_invocation_count"] == 1
