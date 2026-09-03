"""models pricing catalog

Revision ID: 0003
Revises: 0002
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_models_table = sa.table(
    "models",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("provider", sa.String),
    sa.column("model_name", sa.String),
    sa.column("input_cost_per_mtok", sa.Integer),
    sa.column("output_cost_per_mtok", sa.Integer),
    sa.column("enabled", sa.Boolean),
)


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False, unique=True),
        sa.Column("input_cost_per_mtok", sa.Integer(), nullable=False),
        sa.Column("output_cost_per_mtok", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.bulk_insert(
        _models_table,
        [
            {
                "id": uuid.uuid4(),
                "provider": "openai",
                "model_name": "gpt-4o",
                "input_cost_per_mtok": 2_500_000,
                "output_cost_per_mtok": 10_000_000,
                "enabled": True,
            },
            {
                "id": uuid.uuid4(),
                "provider": "openai",
                "model_name": "gpt-4o-mini",
                "input_cost_per_mtok": 150_000,
                "output_cost_per_mtok": 600_000,
                "enabled": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("models")