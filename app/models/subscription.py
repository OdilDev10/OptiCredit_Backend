"""Subscription models - Suscripciones de las financieras."""

import uuid
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, DateTime, Enum, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base_class import Base
from app.models.base_model import BaseModel

if TYPE_CHECKING:
    from app.models.lender import Lender


class Subscription(Base, BaseModel):
    """Suscripción de una financiera."""

    __tablename__ = "subscriptions"

    lender_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lenders.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    monthly_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    max_loans: Mapped[Optional[int]] = mapped_column(default=0)

    # Relationships
    lender: Mapped["Lender"] = relationship(back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription {self.plan_name} ({self.status})>"
