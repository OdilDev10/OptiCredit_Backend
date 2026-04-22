"""Customer portal endpoints - /me/* for customers viewing their own loans and payments."""

from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.customer import Customer
from app.models.lender import Lender
from app.models.lender import LenderBankAccount
from app.models.customer_lender_link import CustomerLenderLink
from app.core.enums import LenderStatus, LinkStatus
from app.repositories.customer_repo import CustomerRepository
from app.repositories.loan_repo import LoanRepository, InstallmentRepository
from app.repositories.loan_application_repo import LoanApplicationRepository
from app.repositories.payment_repo import (
    PaymentRepository,
    VoucherRepository,
    OcrResultRepository,
)
from app.services.payment_service import PaymentService
from app.services.voucher_service import VoucherService
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
)
from app.core.error_codes import ErrorCode, get_error_response


router = APIRouter(prefix="/me", tags=["customer-portal"])


class SubmitPaymentRequest(BaseModel):
    """Submit payment request for customer portal."""

    loan_id: str = Field(..., description="Loan ID")
    installment_id: str = Field(..., description="Installment ID")
    amount: Decimal = Field(..., gt=0, description="Payment amount")


class AssociationRequest(BaseModel):
    """Payload for requesting customer association to a lender."""

    lender_id: UUID = Field(..., description="Lender ID to associate with")


async def _ensure_legacy_link(customer: Customer, session: AsyncSession) -> None:
    """Backfill link table from legacy customer.lender_id when needed."""
    if not customer.lender_id:
        return

    existing = await session.execute(
        select(CustomerLenderLink).where(
            CustomerLenderLink.customer_id == customer.id,
            CustomerLenderLink.lender_id == customer.lender_id,
            CustomerLenderLink.status == LinkStatus.LINKED,
        )
    )
    if existing.scalar_one_or_none():
        return

    session.add(
        CustomerLenderLink(
            customer_id=customer.id,
            lender_id=customer.lender_id,
            status=LinkStatus.LINKED,
        )
    )
    await session.commit()


async def _assert_customer_linked_to_lender(
    customer: Customer,
    lender_id: UUID,
    session: AsyncSession,
) -> None:
    """Ensure customer has an active link with the given lender."""
    link_result = await session.execute(
        select(CustomerLenderLink).where(
            CustomerLenderLink.customer_id == customer.id,
            CustomerLenderLink.lender_id == lender_id,
            CustomerLenderLink.status == LinkStatus.LINKED,
        )
    )
    if link_result.scalar_one_or_none() is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=get_error_response(
                ErrorCode.AUTH_PERMISSION_DENIED,
                "No tienes asociación activa con esta financiera",
            ),
        )


async def get_current_customer(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Customer:
    """Get the Customer profile for the authenticated user."""
    repo = CustomerRepository(session)

    # Customer portal is only valid for customer users.
    role_value = getattr(current_user.role, "value", current_user.role)
    if role_value != "customer":
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=get_error_response(
                ErrorCode.AUTH_PERMISSION_DENIED, "Cuenta de cliente requerida"
            ),
        )

    customer = await repo.get_by_user_id(current_user.id)
    if customer:
        return customer

    # Backward compatibility: old customer records may exist without user_id link.
    customer = await repo.get_by_email_and_lender(
        current_user.email, current_user.lender_id
    )
    if not customer:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=get_error_response(
                ErrorCode.NOT_FOUND_CUSTOMER, "No se encontró perfil de cliente"
            ),
        )

    if customer.user_id is None:
        await repo.update(customer, {"user_id": current_user.id})
        await session.commit()

    return customer


@router.get("/loans")
async def get_my_loans(
    lender_id: UUID | None = Query(default=None),
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all loans for the authenticated customer."""
    loan_repo = LoanRepository(session)
    installment_repo = InstallmentRepository(session)

    if lender_id:
        link_result = await session.execute(
            select(CustomerLenderLink).where(
                CustomerLenderLink.customer_id == customer.id,
                CustomerLenderLink.lender_id == lender_id,
                CustomerLenderLink.status == LinkStatus.LINKED,
            )
        )
        if link_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=get_error_response(
                    ErrorCode.AUTH_PERMISSION_DENIED,
                    "No tienes asociación activa con esta financiera",
                ),
            )
        loans = await loan_repo.get_by_customer_and_lender(
            str(customer.id), str(lender_id)
        )
    else:
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


@router.get("/association")
async def get_my_association(
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get customer-to-lender association details."""
    await _ensure_legacy_link(customer, session)
    link_result = await session.execute(
        select(CustomerLenderLink)
        .where(
            CustomerLenderLink.customer_id == customer.id,
            CustomerLenderLink.status == LinkStatus.LINKED,
        )
        .order_by(CustomerLenderLink.created_at.asc())
    )
    link = link_result.scalars().first()
    lender = None
    if link:
        lender_result = await session.execute(
            select(Lender).where(Lender.id == link.lender_id)
        )
        lender = lender_result.scalar_one_or_none()

    return {
        "customer_id": str(customer.id),
        "lender_id": str(link.lender_id) if link else None,
        "lender_legal_name": lender.legal_name if lender else None,
        "lender_commercial_name": lender.commercial_name if lender else None,
        "lender_type": (
            lender.lender_type.value
            if lender and hasattr(lender.lender_type, "value")
            else (str(lender.lender_type) if lender else None)
        ),
        "lender_document_type": lender.document_type if lender else None,
        "lender_document_number": lender.document_number if lender else None,
        "lender_phone": lender.phone if lender else None,
        "lender_email": lender.email if lender else None,
        "lender_address": lender.address_line if lender else None,
        "lender_status": (
            lender.status.value
            if lender and hasattr(lender.status, "value")
            else (str(lender.status) if lender else None)
        ),
    }


@router.get("/associations")
async def list_my_associations(
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List all lenders currently associated to the authenticated customer."""
    await _ensure_legacy_link(customer, session)

    result = await session.execute(
        select(CustomerLenderLink, Lender)
        .join(Lender, Lender.id == CustomerLenderLink.lender_id)
        .where(
            CustomerLenderLink.customer_id == customer.id,
            CustomerLenderLink.status == LinkStatus.LINKED,
        )
        .order_by(CustomerLenderLink.created_at.desc())
    )
    rows = result.all()

    items = [
        {
            "lender_id": str(lender.id),
            "lender_legal_name": lender.legal_name,
            "lender_commercial_name": lender.commercial_name,
            "lender_type": (
                lender.lender_type.value
                if hasattr(lender.lender_type, "value")
                else str(lender.lender_type)
            ),
            "lender_document_type": lender.document_type,
            "lender_document_number": lender.document_number,
            "lender_phone": lender.phone,
            "lender_email": lender.email,
            "lender_address": lender.address_line,
            "lender_status": (
                lender.status.value
                if hasattr(lender.status, "value")
                else str(lender.status)
            ),
        }
        for _, lender in rows
    ]

    return {"items": items, "total": len(items), "skip": 0, "limit": 20}


@router.get("/lenders")
async def list_lenders_for_customer(
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List active lenders available for customer association."""
    await _ensure_legacy_link(customer, session)

    links_result = await session.execute(
        select(CustomerLenderLink).where(CustomerLenderLink.customer_id == customer.id)
    )
    links = links_result.scalars().all()
    associated_lender_ids = {
        str(link.lender_id) for link in links if link.status == LinkStatus.LINKED
    }
    request_status_by_lender = {
        str(link.lender_id): link.status.value for link in links
    }

    query = select(Lender).where(Lender.status == LenderStatus.ACTIVE)
    count_query = select(func.count(Lender.id)).where(
        Lender.status == LenderStatus.ACTIVE
    )

    if search:
        search_filter = or_(
            Lender.legal_name.ilike(f"%{search}%"),
            Lender.commercial_name.ilike(f"%{search}%"),
            Lender.document_number.ilike(f"%{search}%"),
            Lender.address_line.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    result = await session.execute(
        query.order_by(Lender.created_at.desc()).offset(skip).limit(limit)
    )
    lenders = result.scalars().all()

    items = []
    for lender in lenders:
        items.append(
            {
                "id": str(lender.id),
                "legal_name": lender.legal_name,
                "commercial_name": lender.commercial_name,
                "lender_type": (
                    lender.lender_type.value
                    if hasattr(lender.lender_type, "value")
                    else str(lender.lender_type)
                ),
                "document_type": lender.document_type,
                "document_number": lender.document_number,
                "phone": lender.phone,
                "email": lender.email,
                "address": lender.address_line,
                "status": (
                    lender.status.value
                    if hasattr(lender.status, "value")
                    else str(lender.status)
                ),
                "is_associated": str(lender.id) in associated_lender_ids,
                "request_status": request_status_by_lender.get(str(lender.id), "none"),
            }
        )

    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/lenders/{lender_id}/accounts")
async def get_lender_accounts_for_customer(
    lender_id: UUID,
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return active lender bank accounts visible to an associated customer."""
    await _ensure_legacy_link(customer, session)
    await _assert_customer_linked_to_lender(customer, lender_id, session)

    result = await session.execute(
        select(LenderBankAccount)
        .where(
            LenderBankAccount.lender_id == lender_id,
            LenderBankAccount.status == "active",
        )
        .order_by(
            LenderBankAccount.is_primary.desc(), LenderBankAccount.created_at.desc()
        )
    )
    accounts = result.scalars().all()
    return {
        "items": [
            {
                "id": str(acc.id),
                "bank_name": acc.bank_name,
                "account_type": acc.account_type,
                "account_number_masked": acc.account_number_masked,
                "account_holder_name": acc.account_holder_name,
                "currency": acc.currency,
                "is_primary": acc.is_primary,
            }
            for acc in accounts
        ],
        "total": len(accounts),
    }


@router.post("/association/request")
async def request_association(
    request: AssociationRequest,
    current_user: User = Depends(get_current_user),
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create a pending association request for the current customer."""
    await _ensure_legacy_link(customer, session)

    lender_result = await session.execute(
        select(Lender).where(
            Lender.id == request.lender_id,
            Lender.status == LenderStatus.ACTIVE,
        )
    )
    lender = lender_result.scalar_one_or_none()
    if lender is None:
        raise NotFoundException("Lender no encontrado o no disponible")

    existing_link_result = await session.execute(
        select(CustomerLenderLink).where(
            CustomerLenderLink.customer_id == customer.id,
            CustomerLenderLink.lender_id == lender.id,
        )
    )
    existing_link = existing_link_result.scalar_one_or_none()
    if existing_link and existing_link.status == LinkStatus.LINKED:
        return {
            "message": "Ya estás asociado a esta financiera",
            "lender_id": str(lender.id),
            "status": "already_linked",
        }
    if existing_link and existing_link.status == LinkStatus.PENDING:
        return {
            "message": "Ya tienes una solicitud pendiente con esta financiera",
            "lender_id": str(lender.id),
            "status": "pending",
        }

    if existing_link:
        existing_link.status = LinkStatus.PENDING
    else:
        session.add(
            CustomerLenderLink(
                customer_id=customer.id,
                lender_id=lender.id,
                status=LinkStatus.PENDING,
            )
        )

    await session.commit()

    return {
        "message": "Solicitud de asociación enviada",
        "lender_id": str(lender.id),
        "status": "pending",
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
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=get_error_response(
                ErrorCode.AUTH_PERMISSION_DENIED,
                "No tienes permiso para ver este préstamo",
            ),
        )

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


@router.get("/loan-applications")
async def get_my_loan_applications(
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all loan applications for the authenticated customer."""
    app_repo = LoanApplicationRepository(session)
    applications = await app_repo.get_by_customer(str(customer.id), status=status)

    total = len(applications)
    items = applications[skip : skip + limit]

    return {
        "items": [
            {
                "id": str(app.id),
                "application_number": app.purpose or f"APP-{app.id.hex[:8].upper()}",
                "status": app.status.value,
                "requested_amount": float(app.requested_amount),
                "approved_amount": float(app.approved_amount)
                if app.approved_amount
                else None,
                "submitted_at": app.created_at.isoformat(),
                "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None,
                "rejection_reason": app.review_notes
                if app.status.value == "rejected"
                else None,
            }
            for app in items
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/payments")
async def get_my_payments(
    lender_id: UUID | None = Query(default=None),
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get all payments for the authenticated customer."""
    payment_repo = PaymentRepository(session)
    voucher_repo = VoucherRepository(session)

    payments = await payment_repo.get_by_customer(str(customer.id))
    if lender_id:
        link_result = await session.execute(
            select(CustomerLenderLink).where(
                CustomerLenderLink.customer_id == customer.id,
                CustomerLenderLink.lender_id == lender_id,
                CustomerLenderLink.status == LinkStatus.LINKED,
            )
        )
        if link_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=get_error_response(
                    ErrorCode.AUTH_PERMISSION_DENIED,
                    "No tienes asociación activa con esta financiera",
                ),
            )
        payments = [payment for payment in payments if payment.lender_id == lender_id]

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


@router.post("/payments/{payment_id}/submit-review")
async def submit_my_payment_for_review(
    payment_id: UUID,
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Move customer payment to review once voucher OCR is processed."""
    payment_repo = PaymentRepository(session)
    payment = await payment_repo.get_or_404(str(payment_id))
    if payment.customer_id != customer.id:
        raise ForbiddenException("No tienes permiso para enviar este pago")
    await _assert_customer_linked_to_lender(customer, payment.lender_id, session)

    service = PaymentService(session)
    return await service.submit_for_review(str(payment_id), str(payment.lender_id))


@router.get("/payments/{payment_id}")
async def get_my_payment_detail(
    payment_id: UUID,
    customer: Customer = Depends(get_current_customer),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get payment details for the authenticated customer."""
    payment_repo = PaymentRepository(session)
    voucher_repo = VoucherRepository(session)
    ocr_repo = OcrResultRepository(session)

    payment = await payment_repo.get_or_404(str(payment_id))

    if payment.customer_id != customer.id:
        raise ForbiddenException("You do not have permission to view this payment")

    vouchers = await voucher_repo.get_by_payment(str(payment.id))

    voucher_data = []
    for voucher in vouchers:
        ocr = await ocr_repo.get_by_voucher(str(voucher.id))
        voucher_data.append(
            {
                "voucher_id": str(voucher.id),
                "file_url": voucher.original_file_url,
                "status": voucher.status.value,
                "uploaded_at": voucher.created_at.isoformat(),
                "ocr_status": ocr.status.value if ocr else None,
                "ocr_confidence": float(ocr.confidence_score) if ocr else None,
                "ocr_detected_amount": float(ocr.detected_amount)
                if ocr and ocr.detected_amount
                else None,
                "ocr_detected_bank": ocr.detected_bank_name if ocr else None,
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
