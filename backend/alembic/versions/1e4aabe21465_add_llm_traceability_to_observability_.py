"""add llm traceability to observability runs

Revision ID: 1e4aabe21465
Revises: c6f3b7d91a20
Create Date: 2026-10-02 21:05:12.099688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e4aabe21465'
down_revision: Union[str, Sequence[str], None] = 'c6f3b7d91a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Añade trazabilidad del proveedor, modelo y número de ejecución."""

    op.add_column(
        "observability_runs",
        sa.Column(
            "execution_number",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "observability_runs",
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "observability_runs",
        sa.Column(
            "model",
            sa.String(length=200),
            nullable=True,
        ),
    )

    # Numera cronológicamente las ejecuciones existentes.
    op.execute(
        sa.text(
            """
            WITH numbered AS (
                SELECT
                    execution_id,
                    ROW_NUMBER() OVER (
                        ORDER BY created_at, execution_id
                    )::integer AS execution_number
                FROM observability_runs
            )
            UPDATE observability_runs AS target
            SET execution_number = numbered.execution_number
            FROM numbered
            WHERE target.execution_id = numbered.execution_id
            """
        )
    )

    # El proveedor histórico sí es conocido.
    op.execute(
        sa.text(
            """
            UPDATE observability_runs
            SET provider = 'openrouter'
            WHERE provider IS NULL
            """
        )
    )

    # El modelo histórico no se almacenó.
    op.execute(
        sa.text(
            """
            UPDATE observability_runs
            SET model = 'not_recorded'
            WHERE model IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE SEQUENCE
            observability_runs_execution_number_seq
            """
        )
    )

    op.execute(
        sa.text(
            """
            SELECT setval(
                'observability_runs_execution_number_seq',
                COALESCE(
                    (
                        SELECT MAX(execution_number)
                        FROM observability_runs
                    ),
                    0
                ) + 1,
                false
            )
            """
        )
    )

    op.alter_column(
        "observability_runs",
        "execution_number",
        nullable=False,
        server_default=sa.text(
            "nextval("
            "'observability_runs_execution_number_seq'"
            "::regclass)"
        ),
    )

    op.alter_column(
        "observability_runs",
        "provider",
        nullable=False,
    )

    op.alter_column(
        "observability_runs",
        "model",
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_observability_runs_execution_number",
        "observability_runs",
        ["execution_number"],
    )

    op.execute(
        sa.text(
            """
            ALTER SEQUENCE
            observability_runs_execution_number_seq
            OWNED BY observability_runs.execution_number
            """
        )
    )


def downgrade() -> None:
    """Elimina la trazabilidad añadida."""

    op.drop_constraint(
        "uq_observability_runs_execution_number",
        "observability_runs",
        type_="unique",
    )

    op.alter_column(
        "observability_runs",
        "execution_number",
        server_default=None,
    )

    op.drop_column(
        "observability_runs",
        "model",
    )

    op.drop_column(
        "observability_runs",
        "provider",
    )

    op.drop_column(
        "observability_runs",
        "execution_number",
    )

    op.execute(
        sa.text(
            """
            DROP SEQUENCE IF EXISTS
            observability_runs_execution_number_seq
            """
        )
    )