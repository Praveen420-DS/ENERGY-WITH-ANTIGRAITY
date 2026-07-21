from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    anomaly_type: Mapped[str] = mapped_column(String(50), default="spike")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    actual_kwh: Mapped[float] = mapped_column(Float)
    expected_kwh: Mapped[float] = mapped_column(Float)
    deviation_pct: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    meter: Mapped["Meter"] = relationship(back_populates="anomalies")
