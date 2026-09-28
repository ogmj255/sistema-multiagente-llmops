from uuid import UUID

from app.schemas.observability import ObservabilitySummary
from app.services import observability_persistence


class FakeSession:
    """Simula una sesión SQLAlchemy para tests unitarios."""

    def __init__(
        self,
        *,
        scalar_results: list[object] | None = None,
    ) -> None:
        self.added: list[object] = []
        self.committed = False
        self.statement = None
        self.scalar_results = scalar_results or []

    def __enter__(self):
        return self

    def __exit__(
        self,
        _exc_type,
        _exc_value,
        _traceback,
    ) -> None:
        return None

    def add(
        self,
        record: object,
    ) -> None:
        self.added.append(record)

    def commit(self) -> None:
        self.committed = True

    def scalars(
        self,
        statement,
    ):
        self.statement = statement
        return self.scalar_results


def test_save_observability_run_persists_real_metrics(
    monkeypatch,
) -> None:
    session = FakeSession()

    monkeypatch.setattr(
        observability_persistence,
        "SessionLocal",
        lambda: session,
    )

    execution_id = (
        "550e8400-e29b-41d4-a716-446655440000"
    )

    summary = ObservabilitySummary(
        status="partial",
        duration_ms=1500.5,
        prompt_tokens=300,
        completion_tokens=60,
        total_tokens=360,
        cost_usd=0.005,
        error_count=2,
        llm_invocation_count=2,
    )

    observability_persistence.save_observability_run(
        execution_id=execution_id,
        summary=summary,
    )

    assert len(session.added) == 1
    assert session.committed is True

    record = session.added[0]

    assert record.execution_id == UUID(execution_id)
    assert record.status == "partial"
    assert record.duration_ms == 1500.5
    assert record.prompt_tokens == 300
    assert record.completion_tokens == 60
    assert record.total_tokens == 360
    assert record.cost_usd == 0.005
    assert record.error_count == 2
    assert record.llm_invocation_count == 2


def test_save_observability_run_preserves_missing_cost(
    monkeypatch,
) -> None:
    session = FakeSession()

    monkeypatch.setattr(
        observability_persistence,
        "SessionLocal",
        lambda: session,
    )

    observability_persistence.save_observability_run(
        execution_id=(
            "550e8400-e29b-41d4-a716-446655440001"
        ),
        summary=ObservabilitySummary(
            status="success",
            duration_ms=500.0,
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            cost_usd=None,
            error_count=0,
            llm_invocation_count=1,
        ),
    )

    record = session.added[0]

    assert record.cost_usd is None


def test_list_recent_observability_runs_uses_database(
    monkeypatch,
) -> None:
    expected = [
        object(),
        object(),
    ]
    session = FakeSession(
        scalar_results=expected,
    )

    monkeypatch.setattr(
        observability_persistence,
        "SessionLocal",
        lambda: session,
    )

    result = (
        observability_persistence
        .list_recent_observability_runs(
            limit=25,
        )
    )

    assert result == expected
    assert session.statement is not None
