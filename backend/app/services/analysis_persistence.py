from hashlib import sha256
from typing import Literal
from uuid import UUID

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import AnalysisRun
from app.schemas.orchestration import PipelineError
from app.schemas.report import AnalysisReport

PersistedStatus = Literal[
    "success",
    "partial",
]


def calculate_content_hash(
    cleaned_text: str,
) -> str:
    """Calcula la huella SHA-256 del contenido contractual limpio."""

    return sha256(
        cleaned_text.encode("utf-8")
    ).hexdigest()


def find_successful_analysis(
    source_url: str,
    content_hash: str,
) -> AnalysisRun | None:
    """Busca un análisis exitoso de la misma versión contractual."""

    statement = (
        select(AnalysisRun)
        .where(
            AnalysisRun.source_url == source_url,
            AnalysisRun.content_hash == content_hash,
            AnalysisRun.status == "success",
        )
        .order_by(
            AnalysisRun.created_at.desc()
        )
        .limit(1)
    )

    with SessionLocal() as database:
        return database.scalar(statement)


def get_analysis_by_execution_id(
    execution_id: UUID,
) -> AnalysisRun | None:
    """Recupera una ejecución persistida mediante su identificador."""

    with SessionLocal() as database:
        return database.get(
            AnalysisRun,
            execution_id,
        )


def save_analysis(
    *,
    execution_id: str,
    source_url: str,
    content_hash: str,
    status: PersistedStatus,
    report: AnalysisReport,
    errors: list[PipelineError],
    attempts: dict[str, int],
) -> None:
    """Persiste el resultado estructurado de una ejecución."""

    record = AnalysisRun(
        execution_id=UUID(execution_id),
        source_url=source_url,
        content_hash=content_hash,
        status=status,
        report_data=report.model_dump(
            mode="json"
        ),
        errors=[
            dict(error)
            for error in errors
        ],
        attempts=dict(attempts),
    )

    with SessionLocal() as database:
        database.add(record)
        database.commit()
