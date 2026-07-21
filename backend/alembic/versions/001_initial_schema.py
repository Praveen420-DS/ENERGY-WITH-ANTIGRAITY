"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=50), server_default="consumer", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "meters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meter_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("capacity_kw", sa.Float(), nullable=False),
        sa.Column("meter_type", sa.String(length=50), server_default="commercial", nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_meters_id"), "meters", ["id"], unique=False)
    op.create_index(op.f("ix_meters_meter_id"), "meters", ["meter_id"], unique=True)
    op.create_index(op.f("ix_meters_owner_id"), "meters", ["owner_id"], unique=False)

    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("algorithm", sa.String(length=50), nullable=False),
        sa.Column("horizon", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifact_path", sa.String(length=500), nullable=True),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ml_models_id"), "ml_models", ["id"], unique=False)
    op.create_index(op.f("ix_ml_models_name"), "ml_models", ["name"], unique=False)
    op.create_index(op.f("ix_ml_models_status"), "ml_models", ["status"], unique=False)

    op.create_table(
        "alert_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("meter_id", sa.Integer(), nullable=False),
        sa.Column("threshold_kwh", sa.Float(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sms_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["meter_id"], ["meters.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_configs_id"), "alert_configs", ["id"], unique=False)
    op.create_index(op.f("ix_alert_configs_meter_id"), "alert_configs", ["meter_id"], unique=False)
    op.create_index(op.f("ix_alert_configs_user_id"), "alert_configs", ["user_id"], unique=False)

    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meter_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("anomaly_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("actual_kwh", sa.Float(), nullable=False),
        sa.Column("expected_kwh", sa.Float(), nullable=False),
        sa.Column("deviation_pct", sa.Float(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["meter_id"], ["meters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_anomalies_id"), "anomalies", ["id"], unique=False)
    op.create_index(op.f("ix_anomalies_meter_id"), "anomalies", ["meter_id"], unique=False)
    op.create_index(op.f("ix_anomalies_timestamp"), "anomalies", ["timestamp"], unique=False)

    op.create_table(
        "energy_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meter_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("consumption_kwh", sa.Float(), nullable=False),
        sa.Column("voltage", sa.Float(), nullable=True),
        sa.Column("current", sa.Float(), nullable=True),
        sa.Column("power", sa.Float(), nullable=True),
        sa.Column("power_factor", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), server_default="smart_meter", nullable=False),
        sa.Column("is_valid", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["meter_id"], ["meters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_energy_records_id"), "energy_records", ["id"], unique=False)
    op.create_index(op.f("ix_energy_records_meter_id"), "energy_records", ["meter_id"], unique=False)
    op.create_index(op.f("ix_energy_records_timestamp"), "energy_records", ["timestamp"], unique=False)

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meter_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("horizon", sa.String(length=50), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("target_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("predicted_kwh", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["meter_id"], ["meters.id"]),
        sa.ForeignKeyConstraint(["model_id"], ["ml_models.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_predictions_id"), "predictions", ["id"], unique=False)
    op.create_index(op.f("ix_predictions_meter_id"), "predictions", ["meter_id"], unique=False)
    op.create_index(op.f("ix_predictions_model_id"), "predictions", ["model_id"], unique=False)
    op.create_index(op.f("ix_predictions_target_start"), "predictions", ["target_start"], unique=False)


def downgrade() -> None:
    op.drop_table("predictions")
    op.drop_table("energy_records")
    op.drop_table("anomalies")
    op.drop_table("alert_configs")
    op.drop_table("ml_models")
    op.drop_table("meters")
    op.drop_table("users")
