"""tenant monthly budget

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("monthly_budget_micros", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "monthly_budget_micros")