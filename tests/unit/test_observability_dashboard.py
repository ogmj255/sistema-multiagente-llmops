from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.services.observability_dashboard import (
    build_llmops_dashboard,
)


def test_build_llmops_dashboard_aggregates_real_runs() -> None:
    now = datetime.now(UTC)

    runs = [
        SimpleNamespace(
            execution_id=uuid4(),
            status="success",
            duration_ms=1000.0,
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            cost_usd=0.002,
            error_count=0,
            llm_invocation_count=1,
            created_at=now,
        ),
        SimpleNamespace(
            execution_id=uuid4(),
            status="partial",
            duration_ms=3000.0,
            prompt_tokens=200,
            completion_tokens=40,
            total_tokens=240,
            cost_usd=0.003,
            error_count=2,
            llm_invocation_count=2,
            created_at=now,
        ),
    ]

    dashboard = build_llmops_dashboard(runs)

    assert dashboard.total_executions == 2
    assert dashboard.average_latency_ms == 2000.0
    assert dashboard.total_tokens == 360
    assert dashboard.total_cost_usd == 0.005
    assert dashboard.error_rate_percent == 50.0
    assert dashboard.total_errors == 2
    assert len(dashboard.executions) == 2


def test_build_llmops_dashboard_without_reported_costs() -> None:
    now = datetime.now(UTC)

    runs = [
        SimpleNamespace(
            execution_id=uuid4(),
            status="success",
            duration_ms=500.0,
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            cost_usd=None,
            error_count=0,
            llm_invocation_count=1,
            created_at=now,
        )
    ]

    dashboard = build_llmops_dashboard(runs)

    assert dashboard.total_cost_usd is None
    assert dashboard.error_rate_percent == 0.0


def test_build_llmops_dashboard_empty_history() -> None:
    dashboard = build_llmops_dashboard([])

    assert dashboard.total_executions == 0
    assert dashboard.average_latency_ms == 0.0
    assert dashboard.total_tokens == 0
    assert dashboard.total_cost_usd is None
    assert dashboard.error_rate_percent == 0.0
    assert dashboard.total_errors == 0
    assert dashboard.executions == []
