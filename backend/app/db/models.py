from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AnalysisRun(Base):
    """Representa un análisis contractual persistido."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'partial')",
            name="ck_analysis_runs_status",
        ),
        Index(
            "ix_analysis_runs_source_hash",
            "source_url",
            "content_hash",
        ),
    )

    execution_id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
    )
    source_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    report_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    errors: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    attempts: Mapped[dict[str, int]] = mapped_column(
        JSONB,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

class ObservabilityRun(Base):
    """Representa las métricas LLMOps persistidas de una ejecución."""

    __tablename__ = "observability_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'partial', 'error')",
            name="ck_observability_runs_status",
        ),
        Index(
            "ix_observability_runs_created_at",
            "created_at",
        ),
        UniqueConstraint(
            "execution_number",
            name="uq_observability_runs_execution_number",
        ),
    )
    execution_id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
    )
    execution_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text(
            "nextval("
            "'observability_runs_execution_number_seq'"
            "::regclass)"
        ),
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    platform: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    duration_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    cost_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    llm_invocation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )