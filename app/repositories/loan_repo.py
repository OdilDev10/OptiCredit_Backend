"""Loan repository - database access for loans and installments."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import Optional
from app.repositories.base import BaseRepository
from app.models.loan import (
    Loan,
    Installment,
    Disbursement,
    LoanStatus,
    InstallmentStatus,
)


class LoanRepository(BaseRepository[Loan]):
    """Repository for loan operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Loan)

    async def get_by_lender(
        self, lender_id: str, status: Optional[LoanStatus] = None
    ) -> list[Loan]:
        """Get all loans for a lender."""
        query = select(Loan).where(Loan.lender_id == lender_id)
        if status:
            query = query.where(Loan.status == status)
        query = query.order_by(desc(Loan.created_at))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_customer_and_lender(
        self, customer_id: str, lender_id: str
    ) -> list[Loan]:
        """Get all loans for a customer from a specific lender."""
        query = (
            select(Loan)
            .where(
                and_(
                    Loan.customer_id == customer_id,
                    Loan.lender_id == lender_id,
                )
            )
            .order_by(desc(Loan.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_loan_number(self, loan_number: str) -> Optional[Loan]:
        """Get loan by unique loan number."""
        query = select(Loan).where(Loan.loan_number == loan_number)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_application_id(self, application_id: str) -> Optional[Loan]:
        """Get loan created from application."""
        query = select(Loan).where(Loan.loan_application_id == application_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def count_active_by_customer(self, customer_id: str, lender_id: str) -> int:
        """Count active loans for customer."""
        query = select(Loan).where(
            and_(
                Loan.customer_id == customer_id,
                Loan.lender_id == lender_id,
                Loan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE]),
            )
        )
        result = await self.session.execute(query)
        return len(result.scalars().all())

    async def get_by_customer(self, customer_id: str) -> list[Loan]:
        """Get all loans for a customer."""
        query = (
            select(Loan)
            .where(Loan.customer_id == customer_id)
            .order_by(desc(Loan.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()


class InstallmentRepository(BaseRepository[Installment]):
    """Repository for installment operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Installment)

    async def get_by_loan(self, loan_id: str) -> list[Installment]:
        """Get all installments for a loan."""
        query = (
            select(Installment)
            .where(Installment.loan_id == loan_id)
            .order_by(Installment.installment_number)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_pending_by_loan(self, loan_id: str) -> list[Installment]:
        """Get unpaid installments for a loan."""
        query = (
            select(Installment)
            .where(
                and_(
                    Installment.loan_id == loan_id,
                    Installment.status.in_(
                        [
                            InstallmentStatus.PENDING,
                            InstallmentStatus.PARTIAL,
                            InstallmentStatus.OVERDUE,
                        ]
                    ),
                )
            )
            .order_by(Installment.due_date)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_loan_and_number(
        self, loan_id: str, installment_number: int
    ) -> Optional[Installment]:
        """Get specific installment by loan and number."""
        query = select(Installment).where(
            and_(
                Installment.loan_id == loan_id,
                Installment.installment_number == installment_number,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def count_overdue(self, loan_id: str) -> int:
        """Count overdue installments for loan."""
        query = select(Installment).where(
            and_(
                Installment.loan_id == loan_id,
                Installment.status == InstallmentStatus.OVERDUE,
            )
        )
        result = await self.session.execute(query)
        return len(result.scalars().all())


class DisbursementRepository(BaseRepository[Disbursement]):
    """Repository for disbursement operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Disbursement)

    async def get_by_loan(self, loan_id: str) -> list[Disbursement]:
        """Get all disbursements for a loan."""
        query = (
            select(Disbursement)
            .where(Disbursement.loan_id == loan_id)
            .order_by(Disbursement.created_at)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_completed_for_loan(self, loan_id: str) -> Optional[Disbursement]:
        """Get completed disbursement for a loan."""
        query = select(Disbursement).where(
            and_(
                Disbursement.loan_id == loan_id,
                Disbursement.status == "completed",
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
