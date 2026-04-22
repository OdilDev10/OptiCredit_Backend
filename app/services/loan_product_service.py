"""Service for loan product business logic."""

from uuid import UUID
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loan_product import LoanProduct
from app.repositories.loan_product_repo import LoanProductRepository
from app.core.exceptions import ValidationException


class LoanProductService:
    """Service for loan product operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LoanProductRepository(session)

    async def create_product(
        self,
        lender_id: UUID,
        name: str,
        description: str,
        tier: str = "standard",
        min_amount: float = 1000,
        max_amount: float = 500000,
        min_installments: int = 1,
        max_installments: int = 84,
        annual_interest_rate: float = 0.18,
        example_amount: Optional[float] = None,
        example_monthly_payment: Optional[float] = None,
        is_active: bool = True,
        is_featured: bool = False,
        sort_order: int = 0,
    ) -> LoanProduct:
        """Create a new loan product."""
        if min_amount >= max_amount:
            raise ValidationException("min_amount must be less than max_amount")
        if min_installments > max_installments:
            raise ValidationException(
                "min_installments must be less than max_installments"
            )
        if annual_interest_rate < 0 or annual_interest_rate > 1:
            raise ValidationException("annual_interest_rate must be between 0 and 1")

        if example_amount is None:
            example_amount = min(max_amount, 50000)
        if example_monthly_payment is None:
            example_monthly_payment = self._calculate_monthly_payment(
                example_amount, annual_interest_rate, 24
            )

        product = LoanProduct(
            lender_id=lender_id,
            name=name,
            description=description,
            tier=tier.lower(),
            min_amount=float(min_amount),
            max_amount=float(max_amount),
            min_installments=min_installments,
            max_installments=max_installments,
            annual_interest_rate=float(annual_interest_rate),
            example_amount=float(example_amount),
            example_monthly_payment=float(example_monthly_payment),
            is_active=is_active,
            is_featured=is_featured,
            sort_order=sort_order,
        )

        self.session.add(product)
        await self.session.flush()
        return product

    async def update_product(
        self,
        product_id: UUID,
        lender_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tier: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        min_installments: Optional[int] = None,
        max_installments: Optional[int] = None,
        annual_interest_rate: Optional[float] = None,
        example_amount: Optional[float] = None,
        example_monthly_payment: Optional[float] = None,
        is_active: Optional[bool] = None,
        is_featured: Optional[bool] = None,
        sort_order: Optional[int] = None,
    ) -> LoanProduct:
        """Update an existing loan product."""
        product = await self.repo.get_or_404(product_id, error_code="PRODUCT_NOT_FOUND")

        if str(product.lender_id) != str(lender_id):
            raise ValidationException("Product does not belong to this lender")

        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if tier is not None:
            product.tier = tier.lower()
        if min_amount is not None:
            product.min_amount = float(min_amount)
        if max_amount is not None:
            product.max_amount = float(max_amount)
        if min_installments is not None:
            product.min_installments = min_installments
        if max_installments is not None:
            product.max_installments = max_installments
        if annual_interest_rate is not None:
            product.annual_interest_rate = float(annual_interest_rate)
        if example_amount is not None:
            product.example_amount = float(example_amount)
        if example_monthly_payment is not None:
            product.example_monthly_payment = float(example_monthly_payment)
        if is_active is not None:
            product.is_active = is_active
        if is_featured is not None:
            product.is_featured = is_featured
        if sort_order is not None:
            product.sort_order = sort_order

        await self.session.flush()
        return product

    async def delete_product(self, product_id: UUID, lender_id: UUID) -> None:
        """Delete a loan product."""
        product = await self.repo.get_or_404(product_id, error_code="PRODUCT_NOT_FOUND")
        if str(product.lender_id) != str(lender_id):
            raise ValidationException("Product does not belong to this lender")
        await self.session.delete(product)
        await self.session.flush()

    async def get_lender_products(
        self,
        lender_id: UUID,
        active_only: bool = False,
    ) -> list[LoanProduct]:
        """Get all products for a lender."""
        return await self.repo.get_by_lender(lender_id, active_only=active_only)

    async def toggle_active(
        self,
        product_id: UUID,
        lender_id: UUID,
    ) -> LoanProduct:
        """Toggle the active status of a product."""
        product = await self.repo.get_or_404(product_id, error_code="PRODUCT_NOT_FOUND")
        if str(product.lender_id) != str(lender_id):
            raise ValidationException("Product does not belong to this lender")
        product.is_active = not product.is_active
        await self.session.flush()
        return product

    def _calculate_monthly_payment(
        self,
        principal: float,
        annual_rate: float,
        months: int,
    ) -> float:
        """Calculate monthly payment for a loan."""
        if months <= 0:
            return 0
        monthly_rate = annual_rate / 12
        if monthly_rate == 0:
            return round(principal / months, 2)
        payment = (
            principal
            * (monthly_rate * (1 + monthly_rate) ** months)
            / ((1 + monthly_rate) ** months - 1)
        )
        return round(payment, 2)
