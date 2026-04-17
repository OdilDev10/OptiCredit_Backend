"""Customer portal endpoints - /me/* for customers viewing their own loans and payments."""

from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.customer import Customer
from app.repositories.customer_repo import CustomerRepository
from app.repositories.loan_repo import LoanRepository, InstallmentRepository
from app.repositories.payment_repo import PaymentRepository, VoucherRepository
from app.services.payment_service import PaymentService
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
)


router = APIRouter(prefix="/me", tags=["customer-portal"])


class SubmitPaymentRequest(BaseModel):
    """Submit payment request for customer portal."""

    loan_id: str = Field(..., description="Loan ID")
    installment_id: str = Field(..., description="Installment ID")
    amount: Decimal = Field(..., gt=0, description="Payment amount")


async def get_current_customer(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Customer:
    """Get the Customer profile for the authenticated user."""
    if not current_user.customer_profile:
        raise NotFoundException("No customer profile found for this user")
    return current_user.customer_profile


@router.post("/payments")
async def submit_payment(
    request: SubmitPaymentRequest,
    current_user: User = Depends(get_current_user),
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Submit payment for installment (customer portal)."""
    loan_repo = LoanRepository(session)
    installment_repo = InstallmentRepository(session)

    loan = await loan_repo.get_or_404(request.loan_id)
    if loan.customer_id != customer.id:
        raise ForbiddenException("This loan does not belong to your account")

    installment = await installment_repo.get_or_404(request.installment_id)
    if str(installment.loan_id) != request.loan_id:
        raise ValidationException("Installment does not belong to the specified loan")

    service = PaymentService(session)
    try:
        result = await service.submit_payment(
            loan_id=request.loan_id,
            installment_id=request.installment_id,
            customer_id=str(customer.id),
            lender_id=str(loan.lender_id),
            amount=request.amount,
            submitted_by_user_id=str(current_user.id),
            source="customer_portal",
        )
        return result
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/loans")
async def get_my_loans(
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all loans for the authenticated customer."""
    loan_repo = LoanRepository(session)
    installment_repo = InstallmentRepository(session)

    loans = await loan_repo.get_by_customer(str(customer.id))

    items = []
    for loan in loans:
        installments = await installment_repo.get_by_loan(str(loan.id))
        balance = loan.total_amount - sum(inst.amount_paid for inst in installments)

        items.append(
            {
                "loan_id": str(loan.id),
                "loan_number": loan.loan_number,
                "principal": float(loan.principal_amount),
                "total_amount": float(loan.total_amount),
                "balance": float(balance),
                "interest_rate": float(loan.interest_rate),
                "status": loan.status.value,
                "installments_count": loan.installments_count,
                "frequency": loan.frequency,
                "first_due_date": loan.first_due_date.isoformat()
                if loan.first_due_date
                else None,
                "disbursement_date": loan.disbursement_date.isoformat()
                if loan.disbursement_date
                else None,
                "installments": [
                    {
                        "installment_id": str(inst.id),
                        "number": inst.installment_number,
                        "due_date": inst.due_date.isoformat(),
                        "amount": float(inst.amount_due),
                        "paid": float(inst.amount_paid),
                        "status": inst.status.value,
                    }
                    for inst in installments
                ],
                "created_at": loan.created_at.isoformat(),
            }
        )

    return {
        "count": len(items),
        "loans": items,
    }


@router.get("/loans/{loan_id}")
async def get_my_loan_detail(
    loan_id: UUID,
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get loan details for the authenticated customer."""
    loan_repo = LoanRepository(session)
    installment_repo = InstallmentRepository(session)

    loan = await loan_repo.get_or_404(str(loan_id))

    if loan.customer_id != customer.id:
        raise ForbiddenException("You do not have permission to view this loan")

    installments = await installment_repo.get_by_loan(str(loan.id))
    balance = loan.total_amount - sum(inst.amount_paid for inst in installments)

    return {
        "loan_id": str(loan.id),
        "loan_number": loan.loan_number,
        "principal": float(loan.principal_amount),
        "total_amount": float(loan.total_amount),
        "total_interest": float(loan.total_interest_amount),
        "balance": float(balance),
        "interest_rate": float(loan.interest_rate),
        "status": loan.status.value,
        "frequency": loan.frequency,
        "first_due_date": loan.first_due_date.isoformat()
        if loan.first_due_date
        else None,
        "disbursement_date": loan.disbursement_date.isoformat()
        if loan.disbursement_date
        else None,
        "installments": [
            {
                "installment_id": str(inst.id),
                "number": inst.installment_number,
                "due_date": inst.due_date.isoformat(),
                "principal_component": float(inst.principal_component),
                "interest_component": float(inst.interest_component),
                "amount_due": float(inst.amount_due),
                "amount_paid": float(inst.amount_paid),
                "late_fee": float(inst.late_fee_amount),
                "status": inst.status.value,
                "paid_at": inst.paid_at.isoformat() if inst.paid_at else None,
            }
            for inst in installments
        ],
        "created_at": loan.created_at.isoformat(),
    }


@router.get("/payments")
async def get_my_payments(
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all payments for the authenticated customer."""
    payment_repo = PaymentRepository(session)
    voucher_repo = VoucherRepository(session)

    payments = await payment_repo.get_by_customer(str(customer.id))

    items = []
    for payment in payments:
        vouchers = await voucher_repo.get_by_payment(str(payment.id))

        items.append(
            {
                "payment_id": str(payment.id),
                "loan_id": str(payment.loan_id),
                "installment_id": str(payment.installment_id)
                if payment.installment_id
                else None,
                "amount": float(payment.amount),
                "currency": payment.currency,
                "status": payment.status.value,
                "submitted_at": payment.created_at.isoformat(),
                "reviewed_at": payment.reviewed_at.isoformat()
                if payment.reviewed_at
                else None,
                "review_notes": payment.review_notes,
                "vouchers_count": len(vouchers),
            }
        )

    return {
        "count": len(items),
        "payments": items,
    }


@router.get("/payments/{payment_id}")
async def get_my_payment_detail(
    payment_id: UUID,
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get payment details for the authenticated customer."""
    payment_repo = PaymentRepository(session)
    voucher_repo = VoucherRepository(session)

    payment = await payment_repo.get_or_404(str(payment_id))

    if payment.customer_id != customer.id:
        raise ForbiddenException("You do not have permission to view this payment")

    vouchers = await voucher_repo.get_by_payment(str(payment.id))

    voucher_data = []
    for voucher in vouchers:
        voucher_data.append(
            {
                "voucher_id": str(voucher.id),
                "file_url": voucher.original_file_url,
                "status": voucher.status.value,
                "uploaded_at": voucher.created_at.isoformat(),
            }
        )

    return {
        "payment_id": str(payment.id),
        "loan_id": str(payment.loan_id),
        "installment_id": str(payment.installment_id)
        if payment.installment_id
        else None,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "status": payment.status.value,
        "method": payment.method.value,
        "submitted_at": payment.created_at.isoformat(),
        "reviewed_at": payment.reviewed_at.isoformat() if payment.reviewed_at else None,
        "review_notes": payment.review_notes,
        "vouchers": voucher_data,
    }
