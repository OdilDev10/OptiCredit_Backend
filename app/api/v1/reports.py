"""Reports API - Dashboard statistics and analytics."""

from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.dependencies import get_current_user, require_roles
from app.models.user import User
from app.models.loan import Loan, LoanStatus, Installment, InstallmentStatus
from app.models.payment import Payment, PaymentStatus
from app.models.customer import Customer
from app.models.lender import Lender


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard")
async def get_dashboard_stats(
    current_user: User = Depends(require_roles("owner", "manager", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get dashboard statistics for the authenticated lender."""
    lender_id = str(current_user.lender_id)

    customers_count = await session.execute(
        select(func.count(Customer.id)).where(Customer.lender_id == lender_id)
    )
    total_customers = customers_count.scalar() or 0

    active_loans_result = await session.execute(
        select(func.count(Loan.id)).where(
            Loan.lender_id == lender_id,
            Loan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE]),
        )
    )
    active_loans = active_loans_result.scalar() or 0

    pending_payments_result = await session.execute(
        select(func.count(Payment.id)).where(
            Payment.lender_id == lender_id,
            Payment.status == PaymentStatus.UNDER_REVIEW,
        )
    )
    pending_reviews = pending_payments_result.scalar() or 0

    loans_result = await session.execute(
        select(Loan).where(Loan.lender_id == lender_id)
    )
    all_loans = loans_result.scalars().all()

    total_portfolio = sum(float(loan.total_amount) for loan in all_loans)
    total_outstanding = sum(
        float(loan.total_amount)
        for loan in all_loans
        if loan.status in [LoanStatus.ACTIVE, LoanStatus.OVERDUE]
    )

    return {
        "total_customers": total_customers,
        "active_loans": active_loans,
        "pending_reviews": pending_reviews,
        "total_portfolio": total_portfolio,
        "total_outstanding": total_outstanding,
    }


@router.get("/collections")
async def get_collections_report(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(require_roles("owner", "manager", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get collections report for specified days."""
    lender_id = str(current_user.lender_id)
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    result = await session.execute(
        select(Payment).where(
            Payment.lender_id == lender_id,
            Payment.created_at >= cutoff_date,
        )
    )
    payments = result.scalars().all()

    approved = sum(1 for p in payments if p.status == PaymentStatus.APPROVED)
    rejected = sum(1 for p in payments if p.status == PaymentStatus.REJECTED)
    pending = sum(
        1
        for p in payments
        if p.status in [PaymentStatus.SUBMITTED, PaymentStatus.UNDER_REVIEW]
    )

    total_collected = sum(
        float(p.amount) for p in payments if p.status == PaymentStatus.APPROVED
    )

    return {
        "period_days": days,
        "total_payments": len(payments),
        "approved": approved,
        "rejected": rejected,
        "pending_review": pending,
        "total_collected": total_collected,
    }


@router.get("/portfolio")
async def get_portfolio_report(
    current_user: User = Depends(require_roles("owner", "manager")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get loan portfolio breakdown by status."""
    lender_id = str(current_user.lender_id)

    result = await session.execute(select(Loan).where(Loan.lender_id == lender_id))
    loans = result.scalars().all()

    by_status = {}
    for loan in loans:
        status = loan.status.value
        if status not in by_status:
            by_status[status] = {"count": 0, "total_amount": 0}
        by_status[status]["count"] += 1
        by_status[status]["total_amount"] += float(loan.total_amount)

    return {
        "total_loans": len(loans),
        "by_status": by_status,
    }
