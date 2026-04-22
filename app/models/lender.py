"""Lender models - Financieras y prestamistas."""

import uuid
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, DateTime, Date, Enum, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base_class import Base
from app.models.base_model import BaseModel
from app.core.enums import LenderType, LenderStatus

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.customer import Customer
    from app.models.subscription import Subscription
    from app.models.bank_account import LenderBankAccount
    from app.models.lender_invitation import LenderInvitation


class Lender(Base, BaseModel):
    """Entidad prestamista/financiera."""

    __tablename__ = "lenders"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    commercial_name: Mapped[Optional[str]] = mapped_column(String(255))
    lender_type: Mapped[LenderType] = mapped_column(Enum(LenderType), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    document_number: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address_line: Mapped[Optional[str]] = mapped_column(String(255))
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[LenderStatus] = mapped_column(
        Enum(LenderStatus), default=LenderStatus.PENDING
    )
    subscription_plan: Mapped[Optional[str]] = mapped_column(String(50))
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500))
    subscription_starts_at: Mapped[Optional[datetime]] = mapped_column(Date)
    subscription_ends_at: Mapped[Optional[datetime]] = mapped_column(Date)

    bank_accounts: Mapped[list["LenderBankAccount"]] = relationship(
        back_populates="lender", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(
        back_populates="lender", cascade="all, delete-orphan"
    )
    customers: Mapped[list["Customer"]] = relationship(
        back_populates="lender", cascade="all, delete-orphan"
    )
    invitations: Mapped[list["LenderInvitation"]] = relationship(
        back_populates="lender", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="lender", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lender {self.commercial_name or self.legal_name}>"


class LenderInvitation(Base, BaseModel):
    """Código de invitación para vincular clientes."""

    __tablename__ = "lender_invitations"

    lender_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lenders.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    used_by_customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="active")

    lender: Mapped[Lender] = relationship(back_populates="invitations")

    def __repr__(self) -> str:
        return f"<LenderInvitation {self.code[:8]}...>"


class LenderBankAccount(Base, BaseModel):
    """Cuenta bancaria receptora de la financiera."""

    __tablename__ = "lender_bank_accounts"

    lender_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lenders.id", ondelete="CASCADE"),
        nullable=False,
    )
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)
    account_number_masked: Mapped[str] = mapped_column(String(50), nullable=False)
    account_holder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="DOP")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="active")

    lender: Mapped[Lender] = relationship(back_populates="bank_accounts")

    def __repr__(self) -> str:
        return f"<LenderBankAccount {self.account_number_masked}>"
