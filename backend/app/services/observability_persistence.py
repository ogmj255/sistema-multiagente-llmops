from uuid import UUID

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import ObservabilityRun
from app.schemas.observability import ObservabilitySummary


def save_observability_run(
    *,
    execution_id: str,
    summary: ObservabilitySummary,
) -> None:
    """Persiste las métricas LLMOps de una ejecución."""

    record = ObservabilityRun(
        execution_id=UUID(execution_id),
        status=summary.status,
        duration_ms=summary.duration_ms,
        prompt_tokens=summary.prompt_tokens,
        completion_tokens=summary.completion_tokens,
        total_tokens=summary.total_tokens,
        cost_usd=summary.cost_usd,
        error_count=summary.error_count,
        llm_invocation_count=summary.llm_invocation_count,
    )

    with SessionLocal() as database:
        database.add(record)
        database.commit()


def list_recent_observability_runs(
    *,
    limit: int = 50,
) -> list[ObservabilityRun]:
    """Recupera las ejecuciones LLMOps más recientes."""

    statement = (
        select(ObservabilityRun)
        .order_by(
            ObservabilityRun.created_at.desc()
        )
        .limit(limit)
    )

    with SessionLocal() as database:
        return list(
            database.scalars(statement)
        )
