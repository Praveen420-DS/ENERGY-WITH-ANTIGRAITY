"""Prevent duplicate anomaly records for the same meter and observation."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    duplicates = connection.execute(
        sa.text(
            "SELECT meter_id, timestamp, COUNT(*) AS duplicate_count "
            "FROM anomalies GROUP BY meter_id, timestamp HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicates is not None:
        raise RuntimeError(
            "Cannot add anomaly identity constraint: existing duplicate rows "
            f"were found for meter_id={duplicates.meter_id} at "
            f"timestamp={duplicates.timestamp}. Reconcile these records before retrying."
        )
    op.create_unique_constraint(
        "uq_anomalies_meter_timestamp", "anomalies", ["meter_id", "timestamp"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_anomalies_meter_timestamp", "anomalies", type_="unique")
