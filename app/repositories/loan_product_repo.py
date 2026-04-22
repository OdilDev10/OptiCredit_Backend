"""Repository for LoanProduct persistence operations."""

from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loan_product import LoanProduct
from app.repositories.base import BaseRepository


class LoanProductRepository(BaseRepository[LoanProduct]):
    """Repository for LoanProduct operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, LoanProduct)

    async def get_by_lender(
        self,
        lender_id: UUID,
        active_only: bool = False,
    ) -> list[LoanProduct]:
        """Get all products for a lender."""
        stmt = select(LoanProduct).where(LoanProduct.lender_id == lender_id)
        if active_only:
            stmt = stmt.where(LoanProduct.is_active == True)
        stmt = stmt.order_by(LoanProduct.sort_order, LoanProduct.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_featured_by_lender(
        self,
        lender_id: UUID,
    ) -> list[LoanProduct]:
        """Get featured products for a lender."""
        stmt = (
            select(LoanProduct)
            .where(
                and_(
                    LoanProduct.lender_id == lender_id,
                    LoanProduct.is_active == True,
                    LoanProduct.is_featured == True,
                )
            )
            .order_by(LoanProduct.sort_order)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
