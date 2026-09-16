"""add cascade_decisions table

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cascade_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_content", sa.Text(), nullable=False),
        sa.Column("tier_model", sa.String(), nullable=False),
        sa.Column("was_low_quality", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cascade_decisions_tenant_id"), "cascade_decisions", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_cascade_decisions_tenant_id"), table_name="cascade_decisions")
    op.drop_table("cascade_decisions")