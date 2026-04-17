"""Payment repository - database access for payments and vouchers."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import Optional
from app.repositories.base import BaseRepository
from app.models.payment import (
    Payment,
    Voucher,
    OcrResult,
    PaymentMatch,
    PaymentStatus,
    VoucherStatus,
)


class PaymentRepository(BaseRepository[Payment]):
    """Repository for payment operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Payment)

    async def get_by_lender(
        self, lender_id: str, status: Optional[PaymentStatus] = None
    ) -> list[Payment]:
        """Get all payments for a lender."""
        query = select(Payment).where(Payment.lender_id == lender_id)
        if status:
            query = query.where(Payment.status == status)
        query = query.order_by(desc(Payment.created_at))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_installment(self, installment_id: str) -> list[Payment]:
        """Get all payments for an installment."""
        query = (
            select(Payment)
            .where(Payment.installment_id == installment_id)
            .order_by(desc(Payment.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_loan(
        self, loan_id: str, status: Optional[PaymentStatus] = None
    ) -> list[Payment]:
        """Get all payments for a loan."""
        query = select(Payment).where(Payment.loan_id == loan_id)
        if status:
            query = query.where(Payment.status == status)
        query = query.order_by(desc(Payment.created_at))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_pending_review(self, lender_id: str) -> list[Payment]:
        """Get payments pending review for a lender."""
        query = (
            select(Payment)
            .where(
                and_(
                    Payment.lender_id == lender_id,
                    Payment.status == PaymentStatus.UNDER_REVIEW,
                )
            )
            .order_by(Payment.created_at)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count_approved_for_installment(self, installment_id: str) -> int:
        """Count approved payments for installment."""
        query = select(Payment).where(
            and_(
                Payment.installment_id == installment_id,
                Payment.status == PaymentStatus.APPROVED,
            )
        )
        result = await self.session.execute(query)
        return len(result.scalars().all())

    async def get_by_customer(self, customer_id: str) -> list[Payment]:
        """Get all payments for a customer."""
        query = (
            select(Payment)
            .where(Payment.customer_id == customer_id)
            .order_by(desc(Payment.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()


class VoucherRepository(BaseRepository[Voucher]):
    """Repository for voucher operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Voucher)

    async def get_by_payment(self, payment_id: str) -> list[Voucher]:
        """Get all vouchers for a payment."""
        query = (
            select(Voucher)
            .where(Voucher.payment_id == payment_id)
            .order_by(desc(Voucher.created_at))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_image_hash(self, image_hash: str) -> Optional[Voucher]:
        """Get voucher by image hash (duplicate detection)."""
        query = select(Voucher).where(Voucher.image_hash == image_hash)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_unprocessed(self, lender_id: str, limit: int = 10) -> list[Voucher]:
        """Get unprocessed vouchers for async OCR processing."""
        # Get vouchers that are uploaded but don't have OCR results yet
        query = (
            select(Voucher)
            .where(
                and_(
                    Voucher.status == VoucherStatus.UPLOADED,
                    ~Voucher.ocr_result.any(),
                )
            )
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()


class OcrResultRepository(BaseRepository[OcrResult]):
    """Repository for OCR result operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, OcrResult)

    async def get_by_voucher(self, voucher_id: str) -> Optional[OcrResult]:
        """Get OCR result for a voucher."""
        query = select(OcrResult).where(OcrResult.voucher_id == voucher_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class PaymentMatchRepository(BaseRepository[PaymentMatch]):
    """Repository for payment match operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, PaymentMatch)

    async def get_by_payment(self, payment_id: str) -> list[PaymentMatch]:
        """Get all matches for a payment."""
        query = select(PaymentMatch).where(PaymentMatch.payment_id == payment_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_for_installment(self, installment_id: str) -> Optional[PaymentMatch]:
        """Get match for installment (usually one-to-one or one-to-many)."""
        query = select(PaymentMatch).where(
            PaymentMatch.installment_id == installment_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
