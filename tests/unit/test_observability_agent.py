from app.agents.observability_agent import (
    build_observability_summary,
)
from app.schemas.observability import LLMInvocationMetrics


def test_observability_agent_consolidates_real_metrics() -> None:
    metrics = [
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
            model="model-a",
            prompt_tokens=200,
            completion_tokens=40,
            total_tokens=240,
            cost_usd=0.003,
        ),
    ]

    summary = build_observability_summary(
        status="partial",
        duration_ms=1500.5,
        llm_metrics=metrics,
        error_count=2,
    )

    assert summary.status == "partial"
    assert summary.duration_ms == 1500.5
    assert summary.prompt_tokens == 300
    assert summary.completion_tokens == 60
    assert summary.total_tokens == 360
    assert summary.cost_usd == 0.005
    assert summary.error_count == 2
    assert summary.llm_invocation_count == 2


def test_observability_agent_does_not_invent_cost() -> None:
    metrics = [
        LLMInvocationMetrics(
            provider="openrouter",
            model="model-a",
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            cost_usd=None,
        ),
    ]

    summary = build_observability_summary(
        status="success",
        duration_ms=500.0,
        llm_metrics=metrics,
        error_count=0,
    )

    assert summary.cost_usd is None
    assert summary.total_tokens == 120
    assert summary.llm_invocation_count == 1
