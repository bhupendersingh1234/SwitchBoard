"""add finish_reason to cascade_decisions

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cascade_decisions",
        sa.Column("finish_reason", sa.String(), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("cascade_decisions", "finish_reason")