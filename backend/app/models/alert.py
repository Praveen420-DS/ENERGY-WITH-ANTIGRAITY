from sqlalchemy import Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AlertConfig(Base, TimestampMixin):
    __tablename__ = "alert_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id"), index=True)
    threshold_kwh: Mapped[float] = mapped_column(Float)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    user: Mapped["User"] = relationship(back_populates="alert_configs")
    meter: Mapped["Meter"] = relationship(back_populates="alert_configs")
