from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id"), index=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("ml_models.id"), nullable=True, index=True)
    horizon: Mapped[str] = mapped_column(String(50), default="hourly")
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    target_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    target_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    predicted_kwh: Mapped[float] = mapped_column(Float)
    actual_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    meter: Mapped["Meter"] = relationship(back_populates="predictions")
    model: Mapped["MLModel | None"] = relationship(back_populates="predictions")
