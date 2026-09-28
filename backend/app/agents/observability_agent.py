from collections.abc import Iterable

from app.schemas.observability import (
    LLMInvocationMetrics,
    ObservabilitySummary,
)
from app.schemas.orchestration import PipelineStatus


def build_observability_summary(
    *,
    status: PipelineStatus,
    duration_ms: float,
    llm_metrics: Iterable[LLMInvocationMetrics],
    error_count: int,
) -> ObservabilitySummary:
    """Consolida métricas reales de una ejecución."""

    metrics = tuple(llm_metrics)

    prompt_tokens = sum(
        item.prompt_tokens or 0
        for item in metrics
    )
    completion_tokens = sum(
        item.completion_tokens or 0
        for item in metrics
    )
    total_tokens = sum(
        item.total_tokens or 0
        for item in metrics
    )

    reported_costs = [
        item.cost_usd
        for item in metrics
        if item.cost_usd is not None
    ]

    cost_usd = (
        sum(reported_costs)
        if reported_costs
        else None
    )

    summary_status = (
        status
        if status in {"success", "partial", "error"}
        else "error"
    )

    return ObservabilitySummary(
        status=summary_status,
        duration_ms=duration_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        error_count=error_count,
        llm_invocation_count=len(metrics),
    )
