"""add context to observability runs

Revision ID: c6f3b7d91a20
Revises: 94d7e165308a
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c6f3b7d91a20"
down_revision: str | Sequence[str] | None = "94d7e165308a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Añade contexto identificativo a la observabilidad."""

    op.add_column(
        "observability_runs",
        sa.Column(
            "source_url",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "observability_runs",
        sa.Column(
            "platform",
            sa.Text(),
            nullable=True,
        ),
    )

    # Recupera información de ejecuciones históricas
    # que también tengan un análisis persistido.
    op.execute(
        sa.text(
            """
            UPDATE observability_runs AS observability
            SET
                source_url = analysis.source_url,
                platform = analysis.report_data ->> 'platform'
            FROM analysis_runs AS analysis
            WHERE
                observability.execution_id
                = analysis.execution_id
            """
        )
    )


def downgrade() -> None:
    """Elimina el contexto identificativo."""

    op.drop_column(
        "observability_runs",
        "platform",
    )

    op.drop_column(
        "observability_runs",
        "source_url",
    )