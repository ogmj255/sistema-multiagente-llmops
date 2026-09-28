"""create observability runs

Revision ID: 94d7e165308a
Revises: 51f037f65fa1
Create Date: 2026-09-25 16:49:25.930884

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "94d7e165308a"
down_revision: str | Sequence[str] | None = "51f037f65fa1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "observability_runs",
        sa.Column(
            "execution_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "duration_ms",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "prompt_tokens",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "total_tokens",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "cost_usd",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "error_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "llm_invocation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('success', 'partial', 'error')",
            name="ck_observability_runs_status",
        ),
        sa.PrimaryKeyConstraint(
            "execution_id",
        ),
    )

    op.create_index(
        "ix_observability_runs_created_at",
        "observability_runs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_observability_runs_created_at",
        table_name="observability_runs",
    )
    op.drop_table(
        "observability_runs"
    )
