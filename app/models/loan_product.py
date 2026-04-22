"""Loan Product model - configurable loan products offered by lenders."""

import uuid
from typing import TYPE_CHECKING
from decimal import Decimal

from sqlalchemy import (
    String,
    Numeric,
    Integer,
    Boolean,
    Text,
    ForeignKey,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base_class import Base
from app.models.base_model import BaseModel

if TYPE_CHECKING:
    from app.models.lender import Lender


class ProductTier(str):
    STARTER = "starter"
    STANDARD = "standard"
    PREFERRED = "preferred"


class LoanProduct(Base, BaseModel):
    """Loan product offered by a lender."""

    __tablename__ = "loan_products"

    lender_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProductTier.STANDARD,
    )

    min_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    min_installments: Mapped[int] = mapped_column(Integer, nullable=False)
    max_installments: Mapped[int] = mapped_column(Integer, nullable=False)

    annual_interest_rate: Mapped[float] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )

    example_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    example_monthly_payment: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    lender: Mapped["Lender"] = relationship(foreign_keys=[lender_id])
