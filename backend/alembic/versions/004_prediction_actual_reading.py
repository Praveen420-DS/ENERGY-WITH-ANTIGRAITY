"""Store an optional observed reading with each prediction.

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "predictions",
        sa.Column("actual_kwh", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("predictions", "actual_kwh")
