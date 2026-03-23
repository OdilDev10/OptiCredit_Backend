"""Payment service - manage payment submissions and approvals."""

from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.payment_repo import PaymentRepository, VoucherRepository, OcrResultRepository, PaymentMatchRepository
from app.repositories.loan_repo import InstallmentRepository, LoanRepository
from app.repositories.customer_repo import CustomerRepository
from app.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentSource, Voucher, OcrResult, PaymentMatch
from app.models.loan import Installment, InstallmentStatus
from app.core.exceptions import ValidationException, NotFoundException, ForbiddenException


class PaymentService:
    """Service for payment operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.payment_repo = PaymentRepository(session)
        self.voucher_repo = VoucherRepository(session)
        self.ocr_repo = OcrResultRepository(session)
        self.match_repo = PaymentMatchRepository(session)
        self.installment_repo = InstallmentRepository(session)
        self.loan_repo = LoanRepository(session)
        self.customer_repo = CustomerRepository(session)

    async def submit_payment(
        self,
        loan_id: str,
        installment_id: str,
        customer_id: str,
        lender_id: str,
        amount: Decimal,
        submitted_by_user_id: str,
        source: str = "customer_portal",
    ) -> dict:
        """Submit payment for installment."""
        # Validate installment
        installment = await self.installment_repo.get_or_404(installment_id)
        if installment.loan_id != loan_id:
            raise ValidationException("Installment not linked to loan")

        loan = await self.loan_repo.get_or_404(loan_id)
        if loan.lender_id != lender_id:
            raise ForbiddenException("Not authorized for this loan")

        # Validate payment amount
        if amount <= 0:
            raise ValidationException("Payment amount must be positive")

        if amount > installment.amount_due - installment.amount_paid:
            raise ValidationException("Payment amount exceeds remaining balance")

        # Create payment record
        payment = await self.payment_repo.create({
            "lender_id": lender_id,
            "customer_id": customer_id,
            "loan_id": loan_id,
            "installment_id": installment_id,
            "amount": amount,
            "currency": "RD$",
            "method": PaymentMethod.BANK_TRANSFER,
            "source": PaymentSource(source),
            "status": PaymentStatus.SUBMITTED,
            "submitted_by_user_id": submitted_by_user_id,
        })

        await self.session.commit()

        return {
            "payment_id": str(payment.id),
            "loan_id": str(loan_id),
            "installment_id": str(installment_id),
            "amount": float(amount),
            "status": payment.status.value,
            "message": "Payment submitted successfully",
        }

    async def submit_for_review(self, payment_id: str, lender_id: str) -> dict:
        """Submit payment with vouchers for review."""
        payment = await self.payment_repo.get_or_404(payment_id)

        if payment.lender_id != lender_id:
            raise ForbiddenException("Not authorized to review this payment")

        # Check if has vouchers
        vouchers = await self.voucher_repo.get_by_payment(payment_id)
        if not vouchers:
            raise ValidationException("Payment must have at least one voucher")

        # Check if all vouchers are processed
        for voucher in vouchers:
            if voucher.status != "processed":
                raise ValidationException(f"Voucher {voucher.id} not yet processed")

        # Update status to under review
        payment.status = PaymentStatus.UNDER_REVIEW
        await self.payment_repo.update(payment, {"status": PaymentStatus.UNDER_REVIEW})
        await self.session.commit()

        return {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "message": "Payment submitted for review",
        }

    async def approve_payment(
        self,
        payment_id: str,
        lender_id: str,
        reviewed_by_user_id: str,
        review_notes: str = None,
    ) -> dict:
        """Approve payment and update installment."""
        payment = await self.payment_repo.get_or_404(payment_id)

        if payment.lender_id != lender_id:
            raise ForbiddenException("Not authorized to review this payment")

        if payment.status != PaymentStatus.UNDER_REVIEW:
            raise ValidationException(f"Cannot approve payment with status {payment.status}")

        # Update payment
        payment.status = PaymentStatus.APPROVED
        payment.reviewed_by_user_id = reviewed_by_user_id
        payment.reviewed_at = datetime.now(timezone.utc)
        payment.review_notes = review_notes

        await self.payment_repo.update(payment, {
            "status": PaymentStatus.APPROVED,
            "reviewed_by_user_id": reviewed_by_user_id,
            "reviewed_at": datetime.now(timezone.utc),
            "review_notes": review_notes,
        })

        # Update installment
        installment = await self.installment_repo.get_or_404(payment.installment_id)
        installment.amount_paid += payment.amount

        # Update status based on amount paid
        if installment.amount_paid >= installment.amount_due:
            installment.status = InstallmentStatus.PAID
            installment.paid_at = datetime.utcnow()
        else:
            installment.status = InstallmentStatus.PARTIAL

        await self.installment_repo.update(installment, {
            "amount_paid": installment.amount_paid,
            "status": installment.status,
            "paid_at": installment.paid_at,
        })

        await self.session.commit()

        return {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "installment_status": installment.status.value,
            "message": "Payment approved",
        }

    async def reject_payment(
        self,
        payment_id: str,
        lender_id: str,
        reviewed_by_user_id: str,
        review_notes: str,
    ) -> dict:
        """Reject payment."""
        payment = await self.payment_repo.get_or_404(payment_id)

        if payment.lender_id != lender_id:
            raise ForbiddenException("Not authorized to review this payment")

        if payment.status != PaymentStatus.UNDER_REVIEW:
            raise ValidationException(f"Cannot reject payment with status {payment.status}")

        if not review_notes:
            raise ValidationException("Review notes required for rejection")

        # Update payment
        payment.status = PaymentStatus.REJECTED
        payment.reviewed_by_user_id = reviewed_by_user_id
        payment.reviewed_at = datetime.now(timezone.utc)
        payment.review_notes = review_notes

        await self.payment_repo.update(payment, {
            "status": PaymentStatus.REJECTED,
            "reviewed_by_user_id": reviewed_by_user_id,
            "reviewed_at": datetime.now(timezone.utc),
            "review_notes": review_notes,
        })

        await self.session.commit()

        return {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "message": "Payment rejected",
        }

    async def get_payment_details(self, payment_id: str, lender_id: str) -> dict:
        """Get payment details with vouchers and OCR results."""
        payment = await self.payment_repo.get_or_404(payment_id)

        if payment.lender_id != lender_id:
            raise ForbiddenException("Not authorized to view this payment")

        vouchers = await self.voucher_repo.get_by_payment(payment_id)

        voucher_data = []
        for voucher in vouchers:
            ocr = await self.ocr_repo.get_by_voucher(voucher.id)
            voucher_data.append({
                "voucher_id": str(voucher.id),
                "file_url": voucher.original_file_url,
                "status": voucher.status.value,
                "ocr_result": {
                    "detected_amount": float(ocr.detected_amount) if ocr and ocr.detected_amount else None,
                    "detected_date": ocr.detected_date if ocr else None,
                    "confidence_score": float(ocr.confidence_score) if ocr else None,
                } if ocr else None,
            })

        return {
            "payment_id": str(payment.id),
            "loan_id": str(payment.loan_id),
            "amount": float(payment.amount),
            "status": payment.status.value,
            "submitted_at": payment.created_at.isoformat(),
            "vouchers": voucher_data,
        }

    async def list_pending_payments(self, lender_id: str, limit: int = 50) -> dict:
        """List payments pending review."""
        payments = await self.payment_repo.get_pending_review(lender_id)
        payments = payments[:limit]

        items = []
        for payment in payments:
            customer = await self.customer_repo.get_or_404(payment.customer_id)
            items.append(
                {
                    "payment_id": str(payment.id),
                    "loan_id": str(payment.loan_id),
                    "customer_id": str(payment.customer_id),
                    "customer_name": f"{customer.first_name} {customer.last_name}".strip(),
                    "amount": float(payment.amount),
                    "status": payment.status.value,
                    "submitted_at": payment.created_at.isoformat(),
                }
            )

        return {
            "count": len(payments),
            "payments": items,
        }
