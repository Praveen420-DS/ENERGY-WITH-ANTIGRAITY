from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MLModel(Base):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[str] = mapped_column(String(50))
    algorithm: Mapped[str] = mapped_column(String(50), default="xgboost")
    horizon: Mapped[str] = mapped_column(String(50), default="hourly")
    status: Mapped[str] = mapped_column(String(50), default="training", index=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="model")
