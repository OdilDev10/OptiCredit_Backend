"""Loan Application repository - database access for loan applications."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import Optional
from app.repositories.base import BaseRepository
from app.models.loan_application import LoanApplication, LoanApplicationStatus


class LoanApplicationRepository(BaseRepository[LoanApplication]):
    """Repository for loan application operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, LoanApplication)

    async def get_by_lender(
        self, lender_id: str, status: Optional[LoanApplicationStatus] = None
    ) -> list[LoanApplication]:
        """Get all applications for a lender."""
        query = select(LoanApplication).where(LoanApplication.lender_id == lender_id)
        if status:
            query = query.where(LoanApplication.status == status)
        query = query.order_by(desc(LoanApplication.created_at))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_customer_and_lender(
        self, customer_id: str, lender_id: str
    ) -> list[LoanApplication]:
        """Get all applications for a customer from a specific lender."""
        query = (
            select(LoanApplication)
            .where(
                and_(
                    LoanApplication.customer_id == customer_id,
                    LoanApplication.lender_id == lender_id,
                )
            )
            .order_by(desc(LoanApplication.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_customer(
        self, customer_id: str, status: Optional[str] = None
    ) -> list[LoanApplication]:
        """Get all applications for a customer."""
        query = select(LoanApplication).where(
            LoanApplication.customer_id == customer_id
        )
        if status:
            query = query.where(LoanApplication.status == status)
        query = query.order_by(desc(LoanApplication.created_at))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_pending_review(self, lender_id: str) -> list[LoanApplication]:
        """Get applications pending review for a lender."""
        query = (
            select(LoanApplication)
            .where(
                and_(
                    LoanApplication.lender_id == lender_id,
                    LoanApplication.status == LoanApplicationStatus.UNDER_REVIEW,
                )
            )
            .order_by(LoanApplication.created_at)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_by_lender(
        self, lender_id: str, status: Optional[LoanApplicationStatus] = None
    ) -> int:
        """Count applications for a lender."""
        query = select(LoanApplication).where(LoanApplication.lender_id == lender_id)
        if status:
            query = query.where(LoanApplication.status == status)
        result = await self.session.execute(
            select(LoanApplication).where(LoanApplication.lender_id == lender_id)
        )
        return len(result.scalars().all())
