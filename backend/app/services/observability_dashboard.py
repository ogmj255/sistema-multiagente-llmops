from collections.abc import Iterable

from app.db.models import ObservabilityRun
from app.schemas.observability import (
    LLMOpsDashboardResponse,
    ObservabilityRunResponse,
)


def build_llmops_dashboard(
    runs: Iterable[ObservabilityRun],
) -> LLMOpsDashboardResponse:
    """Construye las métricas agregadas del dashboard LLMOps."""

    records = tuple(runs)
    total_executions = len(records)

    total_duration_ms = sum(
        record.duration_ms
        for record in records
    )

    average_latency_ms = (
        total_duration_ms / total_executions
        if total_executions
        else 0.0
    )

    total_tokens = sum(
        record.total_tokens
        for record in records
    )

    reported_costs = [
        record.cost_usd
        for record in records
        if record.cost_usd is not None
    ]

    total_cost_usd = (
        sum(reported_costs)
        if reported_costs
        else None
    )

    executions_with_errors = sum(
        record.error_count > 0
        for record in records
    )

    error_rate_percent = (
        executions_with_errors
        / total_executions
        * 100
        if total_executions
        else 0.0
    )

    total_errors = sum(
        record.error_count
        for record in records
    )

    executions = [
        ObservabilityRunResponse(
            execution_id=str(record.execution_id),
            execution_number=record.execution_number,
            provider=record.provider,
            model=record.model,
            platform=getattr(
                record,
                "platform",
                None,
            ),
            source_url=getattr(
                record,
                "source_url",
                None,
            ),
            status=record.status,
            duration_ms=record.duration_ms,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            cost_usd=record.cost_usd,
            error_count=record.error_count,
            llm_invocation_count=(
                record.llm_invocation_count
            ),
            created_at=record.created_at,
        )
        for record in records
    ]

    return LLMOpsDashboardResponse(
        total_executions=total_executions,
        average_latency_ms=average_latency_ms,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        error_rate_percent=error_rate_percent,
        total_errors=total_errors,
        executions=executions,
    )