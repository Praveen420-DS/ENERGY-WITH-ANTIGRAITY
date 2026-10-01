"""Register the production V1 model and default electricity meter.

Revision ID: 003
Revises: 002
"""

from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Register the production V1 model if it does not already exist.
    op.execute(
        sa.text(
            """
            INSERT INTO ml_models (
                name,
                version,
                algorithm,
                horizon,
                status,
                metrics,
                artifact_path
            )
            SELECT
                :name,
                :version,
                :algorithm,
                :horizon,
                :status,
                CAST(:metrics AS jsonb),
                :artifact_path
            WHERE NOT EXISTS (
                SELECT 1
                FROM ml_models
                WHERE version = :version
            )
            """
        ).bindparams(
            sa.bindparam("name", "Energy Consumption Random Forest"),
            sa.bindparam("version", "v1.0.0"),
            sa.bindparam("algorithm", "random_forest"),
            sa.bindparam("horizon", "hourly"),
            sa.bindparam("status", "production"),
            sa.bindparam("metrics", "{}"),
            sa.bindparam(
                "artifact_path",
                "models/production/v1.0.0",
            ),
        )
    )

    # Register one application-level electricity meter.
    op.execute(
        sa.text(
            """
            INSERT INTO meters (
                meter_id,
                name,
                location,
                capacity_kw,
                meter_type,
                is_active
            )
            SELECT
                :meter_id,
                :name,
                :location,
                :capacity_kw,
                :meter_type,
                TRUE
            WHERE NOT EXISTS (
                SELECT 1
                FROM meters
                WHERE meter_id = :meter_id
            )
            """
        ).bindparams(
            sa.bindparam("meter_id", "electricity-default"),
            sa.bindparam("name", "Electricity Prediction Meter"),
            sa.bindparam("location", "Production ML API"),
            sa.bindparam("capacity_kw", 0.0),
            sa.bindparam("meter_type", "electricity"),
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM meters
            WHERE meter_id = 'electricity-default'
            """
        )
    )

    op.execute(
        sa.text(
            """
            DELETE FROM ml_models
            WHERE version = 'v1.0.0'
            """
        )
    )
    