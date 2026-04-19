"""Lender dashboard API - dashboard stats, loans, customers, payments, users."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_

from app.db.session import get_db
from app.dependencies import get_lender_context, require_roles
from app.models.user import User
from app.models.customer import Customer
from app.models.loan import Loan, LoanStatus
from app.models.payment import Payment, PaymentStatus
from app.models.customer_lender_link import CustomerLenderLink
from app.models.customer_document import CustomerDocument
from app.core.enums import LinkStatus
from app.schemas.dashboard import (
    LenderDashboardResponse,
    PaginatedLoansResponse,
    PaginatedCustomersResponse,
    PaginatedPaymentsResponse,
    PaginatedUsersResponse,
    LoanKPIs,
    PaymentKPIs,
)
from app.services.dashboard_service import DashboardService
from app.services.payment_service import PaymentService
from app.services.storage_service import storage_service


router = APIRouter(prefix="/lender", tags=["lender"])


@router.get("/dashboard", response_model=LenderDashboardResponse)
async def get_lender_dashboard(
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> LenderDashboardResponse:
    """Get full dashboard with KPIs, charts, and recent activity."""
    service = DashboardService(session)
    data = await service.get_lender_dashboard(lender_id)
    return LenderDashboardResponse(**data)


@router.get("/loans")
async def list_lender_loans(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> PaginatedLoansResponse:
    """List loans for lender with pagination and search."""
    service = DashboardService(session)
    items, total = await service.list_loans(lender_id, search, status, skip, limit)
    return PaginatedLoansResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/loans/kpis")
async def get_loan_kpis(
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> LoanKPIs:
    """Get loan screen KPIs."""
    service = DashboardService(session)
    data = await service.get_loan_kpis(lender_id)
    return LoanKPIs(**data)


@router.get("/customers")
async def list_lender_customers(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> PaginatedCustomersResponse:
    """List customers for lender with pagination and search."""
    service = DashboardService(session)
    items, total = await service.list_customers(lender_id, search, status, skip, limit)
    return PaginatedCustomersResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/payments")
async def list_lender_payments(
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> PaginatedPaymentsResponse:
    """List pending payment vouchers for lender with pagination and search."""
    service = DashboardService(session)
    items, total = await service.list_pending_vouchers(lender_id, search, skip, limit)
    return PaginatedPaymentsResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/payments/kpis")
async def get_payment_kpis(
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> PaymentKPIs:
    """Get payment screen KPIs."""
    service = DashboardService(session)
    data = await service.get_payment_kpis(lender_id)
    return PaymentKPIs(**data)


class ApprovePaymentRequest(BaseModel):
    review_notes: str | None = None


class RejectPaymentRequest(BaseModel):
    reason: str


@router.post("/payments/{payment_id}/approve")
async def approve_payment(
    payment_id: UUID,
    request: ApprovePaymentRequest | None = None,
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Approve a payment voucher."""
    service = PaymentService(session)
    await service.approve_payment(
        str(payment_id),
        lender_id,
        str(current_user.id),
        request.review_notes if request else None,
    )
    return {"success": True, "message": "Payment approved"}


@router.post("/payments/{payment_id}/reject")
async def reject_payment(
    payment_id: UUID,
    request: RejectPaymentRequest,
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a payment voucher with reason."""
    service = PaymentService(session)
    await service.reject_payment(
        str(payment_id), lender_id, str(current_user.id), request.reason
    )
    return {"success": True, "message": "Payment rejected"}


@router.get("/customers/{customer_id}/loans")
async def get_customer_loans_for_lender(
    customer_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get loans for a specific customer in lender scope."""
    service = DashboardService(session)
    items = await service.get_customer_loans(lender_id, str(customer_id), limit)
    return {"items": items, "total": len(items), "limit": limit}


@router.get("/customers/{customer_id}/payments")
async def get_customer_payments_for_lender(
    customer_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get payment history for a specific customer in lender scope."""
    service = DashboardService(session)
    items = await service.get_customer_payment_history(
        lender_id, str(customer_id), limit
    )
    return {"items": items, "total": len(items), "limit": limit}


@router.get("/users")
async def list_lender_users(
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> PaginatedUsersResponse:
    """List users for lender with pagination and search."""
    service = DashboardService(session)
    items, total = await service.list_users(lender_id, search, skip, limit)
    return PaginatedUsersResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/association-requests")
async def list_association_requests(
    status_filter: str = Query(default="pending"),
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List customer association requests for this lender."""
    normalized_status = (status_filter or "pending").strip().lower()
    if normalized_status not in {"pending", "linked", "unlinked", "all"}:
        normalized_status = "pending"

    base_query = (
        select(CustomerLenderLink, Customer)
        .join(Customer, Customer.id == CustomerLenderLink.customer_id)
        .where(CustomerLenderLink.lender_id == lender_id)
    )
    count_query = select(func.count(CustomerLenderLink.id)).where(
        CustomerLenderLink.lender_id == lender_id
    )

    if normalized_status != "all":
        status_enum = LinkStatus(normalized_status)
        base_query = base_query.where(CustomerLenderLink.status == status_enum)
        count_query = count_query.where(CustomerLenderLink.status == status_enum)

    if search:
        search_term = search.strip()
        if search_term:
            search_filter = or_(
                Customer.first_name.ilike(f"%{search_term}%"),
                Customer.last_name.ilike(f"%{search_term}%"),
                Customer.email.ilike(f"%{search_term}%"),
                Customer.document_number.ilike(f"%{search_term}%"),
            )
            base_query = base_query.where(search_filter)
            count_query = count_query.where(search_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    result = await session.execute(
        base_query.order_by(desc(CustomerLenderLink.created_at))
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()

    items = []
    for link, customer in rows:
        items.append(
            {
                "request_id": str(link.id),
                "customer_id": str(customer.id),
                "full_name": f"{customer.first_name} {customer.last_name}",
                "email": customer.email,
                "phone": customer.phone,
                "document_type": customer.document_type,
                "document_number": customer.document_number,
                "status": link.status.value,
                "requested_at": link.created_at.isoformat()
                if link.created_at
                else None,
                "updated_at": link.updated_at.isoformat() if link.updated_at else None,
            }
        )

    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/association-requests/{request_id}/approve")
async def approve_association_request(
    request_id: UUID,
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Approve a pending customer association request."""
    result = await session.execute(
        select(CustomerLenderLink)
        .where(
            CustomerLenderLink.id == request_id,
            CustomerLenderLink.lender_id == lender_id,
        )
        .limit(1)
    )
    link = result.scalar_one_or_none()
    if link is None:
        return {"success": False, "message": "Solicitud no encontrada"}

    link.status = LinkStatus.LINKED

    customer_result = await session.execute(
        select(Customer).where(Customer.id == link.customer_id).limit(1)
    )
    customer = customer_result.scalar_one_or_none()
    if customer and customer.lender_id is None:
        customer.lender_id = UUID(lender_id)

    await session.commit()
    return {
        "success": True,
        "request_id": str(link.id),
        "status": link.status.value,
        "message": "Solicitud aprobada",
    }


@router.post("/association-requests/{request_id}/reject")
async def reject_association_request(
    request_id: UUID,
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a pending customer association request."""
    result = await session.execute(
        select(CustomerLenderLink)
        .where(
            CustomerLenderLink.id == request_id,
            CustomerLenderLink.lender_id == lender_id,
        )
        .limit(1)
    )
    link = result.scalar_one_or_none()
    if link is None:
        return {"success": False, "message": "Solicitud no encontrada"}

    link.status = LinkStatus.UNLINKED
    await session.commit()
    return {
        "success": True,
        "request_id": str(link.id),
        "status": link.status.value,
        "message": "Solicitud rechazada",
    }


@router.get("/customers/{customer_id}/profile")
async def get_customer_profile_for_lender(
    customer_id: UUID,
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer", "agent")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Return rich customer profile for lender detail view."""
    customer_result = await session.execute(
        select(Customer).where(Customer.id == customer_id).limit(1)
    )
    customer = customer_result.scalar_one_or_none()
    if customer is None:
        return {"success": False, "message": "Cliente no encontrado"}

    # Tenant guard: customer belongs to this lender OR has an association link to this lender.
    link_result = await session.execute(
        select(CustomerLenderLink)
        .where(
            CustomerLenderLink.customer_id == customer.id,
            CustomerLenderLink.lender_id == lender_id,
        )
        .limit(1)
    )
    link = link_result.scalar_one_or_none()
    if str(customer.lender_id) != str(lender_id) and link is None:
        return {"success": False, "message": "Cliente fuera de tu cartera"}

    loans_result = await session.execute(
        select(Loan)
        .where(Loan.customer_id == customer.id, Loan.lender_id == lender_id)
        .order_by(desc(Loan.created_at))
    )
    loans = loans_result.scalars().all()

    payments_result = await session.execute(
        select(Payment)
        .where(Payment.customer_id == customer.id, Payment.lender_id == lender_id)
        .order_by(desc(Payment.created_at))
    )
    payments = payments_result.scalars().all()

    documents_result = await session.execute(
        select(CustomerDocument)
        .where(CustomerDocument.customer_id == customer.id)
        .order_by(desc(CustomerDocument.created_at))
    )
    documents = documents_result.scalars().all()

    approved_count = sum(1 for p in payments if p.status == PaymentStatus.APPROVED)
    rejected_count = sum(1 for p in payments if p.status == PaymentStatus.REJECTED)
    under_review_count = sum(
        1
        for p in payments
        if p.status in {PaymentStatus.SUBMITTED, PaymentStatus.UNDER_REVIEW}
    )
    approved_amount = float(
        sum((p.amount for p in payments if p.status == PaymentStatus.APPROVED), start=0)
    )
    active_loan_count = sum(
        1 for loan in loans if loan.status in {LoanStatus.ACTIVE, LoanStatus.OVERDUE}
    )

    loan_history = [
        {
            "loan_id": str(loan.id),
            "loan_number": loan.loan_number,
            "principal_amount": float(loan.principal_amount),
            "total_amount": float(loan.total_amount),
            "status": loan.status.value,
            "created_at": loan.created_at.isoformat() if loan.created_at else None,
        }
        for loan in loans
    ]

    document_items = []
    for doc in documents:
        file_url = None
        try:
            file_url = await storage_service.generate_url(doc.file_path)
        except Exception:
            file_url = None
        document_items.append(
            {
                "id": str(doc.id),
                "document_type": doc.document_type.value
                if hasattr(doc.document_type, "value")
                else str(doc.document_type),
                "status": doc.status,
                "file_name": doc.file_name,
                "file_path": doc.file_path,
                "file_url": file_url,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
                "notes": doc.notes,
            }
        )

    return {
        "success": True,
        "customer": {
            "id": str(customer.id),
            "full_name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email,
            "phone": customer.phone,
            "document_type": customer.document_type,
            "document_number": customer.document_number,
            "status": customer.status.value
            if hasattr(customer.status, "value")
            else str(customer.status),
            "created_at": customer.created_at.isoformat()
            if customer.created_at
            else None,
            "association_status": link.status.value if link else "linked",
        },
        "credit_history": {
            "loan_count": len(loans),
            "active_loan_count": active_loan_count,
            "approved_payments_count": approved_count,
            "under_review_payments_count": under_review_count,
            "rejected_payments_count": rejected_count,
            "approved_payments_amount": approved_amount,
        },
        "loan_history": loan_history,
        "documents": document_items,
    }
