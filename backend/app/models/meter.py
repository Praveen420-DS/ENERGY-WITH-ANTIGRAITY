from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Meter(Base, TimestampMixin):
    __tablename__ = "meters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    meter_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255))
    capacity_kw: Mapped[float] = mapped_column(Float, default=0.0)
    meter_type: Mapped[str] = mapped_column(String(50), default="commercial", server_default="commercial")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    owner: Mapped["User | None"] = relationship(back_populates="meters")
    energy_records: Mapped[list["EnergyRecord"]] = relationship(back_populates="meter")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="meter")
    anomalies: Mapped[list["Anomaly"]] = relationship(back_populates="meter")
    alert_configs: Mapped[list["AlertConfig"]] = relationship(back_populates="meter")
