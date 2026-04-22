"""Admin Reports API - Platform-wide analytics and reports."""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_roles
from app.models.user import User
from app.models.lender import Lender, LenderStatus
from app.models.customer import Customer
from app.models.loan import Loan, LoanStatus
from app.models.payment import Payment, PaymentStatus


router = APIRouter(prefix="/admin/reports", tags=["admin-reports"])


@router.get("/overview")
async def get_admin_overview(
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get platform overview statistics."""

    total_lenders = await session.execute(select(func.count(Lender.id)))
    lenders_count = total_lenders.scalar() or 0

    active_lenders = await session.execute(
        select(func.count(Lender.id)).where(Lender.status == LenderStatus.ACTIVE)
    )
    active_lenders_count = active_lenders.scalar() or 0

    pending_lenders = await session.execute(
        select(func.count(Lender.id)).where(Lender.status == LenderStatus.PENDING)
    )
    pending_lenders_count = pending_lenders.scalar() or 0

    suspended_lenders = await session.execute(
        select(func.count(Lender.id)).where(Lender.status == LenderStatus.SUSPENDED)
    )
    suspended_lenders_count = suspended_lenders.scalar() or 0

    total_customers = await session.execute(select(func.count(Customer.id)))
    customers_count = total_customers.scalar() or 0

    total_loans = await session.execute(select(func.count(Loan.id)))
    loans_count = total_loans.scalar() or 0

    active_loans = await session.execute(
        select(func.count(Loan.id)).where(
            Loan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE])
        )
    )
    active_loans_count = active_loans.scalar() or 0

    portfolio_result = await session.execute(select(func.sum(Loan.total_amount)))
    total_portfolio = float(portfolio_result.scalar() or 0)

    pending_payments = await session.execute(
        select(func.count(Payment.id)).where(
            Payment.status == PaymentStatus.UNDER_REVIEW
        )
    )
    pending_payments_count = pending_payments.scalar() or 0

    return {
        "total_lenders": lenders_count,
        "active_lenders": active_lenders_count,
        "pending_lenders": pending_lenders_count,
        "suspended_lenders": suspended_lenders_count,
        "total_customers": customers_count,
        "total_loans": loans_count,
        "active_loans": active_loans_count,
        "total_portfolio": total_portfolio,
        "pending_payments": pending_payments_count,
    }


@router.get("/lenders-by-plan")
async def get_lenders_by_plan(
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get distribution of lenders by subscription plan."""

    plans = ["basic", "professional", "enterprise"]
    result = {}

    for plan in plans:
        count_result = await session.execute(
            select(func.count(Lender.id)).where(Lender.subscription_plan == plan)
        )
        result[plan] = count_result.scalar() or 0

    return {"distribution": result}


@router.get("/lenders-by-status")
async def get_lenders_by_status(
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get distribution of lenders by status."""

    statuses = ["active", "pending", "suspended", "rejected"]
    result = {}

    for status in statuses:
        status_enum = (
            LenderStatus(status) if status in [s.value for s in LenderStatus] else None
        )
        if status_enum:
            count_result = await session.execute(
                select(func.count(Lender.id)).where(Lender.status == status_enum)
            )
            result[status] = count_result.scalar() or 0

    return {"distribution": result}


@router.get("/recent-activity")
async def get_recent_activity(
    days: int = Query(default=7, ge=1, le=30),
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get recent platform activity."""

    cutoff = datetime.utcnow() - timedelta(days=days)

    new_lenders_result = await session.execute(
        select(func.count(Lender.id)).where(Lender.created_at >= cutoff)
    )
    new_lenders = new_lenders_result.scalar() or 0

    new_customers_result = await session.execute(
        select(func.count(Customer.id)).where(Customer.created_at >= cutoff)
    )
    new_customers = new_customers_result.scalar() or 0

    new_loans_result = await session.execute(
        select(func.count(Loan.id)).where(Loan.created_at >= cutoff)
    )
    new_loans = new_loans_result.scalar() or 0

    recent_payments_result = await session.execute(
        select(func.count(Payment.id)).where(Payment.created_at >= cutoff)
    )
    recent_payments = recent_payments_result.scalar() or 0

    return {
        "period_days": days,
        "new_lenders": new_lenders,
        "new_customers": new_customers,
        "new_loans": new_loans,
        "recent_payments": recent_payments,
    }


@router.get("/top-lenders")
async def get_top_lenders_by_portfolio(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=5, ge=1, le=20),
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get top lenders by portfolio size with pagination."""

    count_result = await session.execute(select(func.count(Lender.id)))
    total = count_result.scalar() or 0

    result = await session.execute(
        select(Lender).order_by(desc(Lender.created_at)).offset(skip).limit(limit)
    )
    lenders = result.scalars().all()

    items = []
    for lender in lenders:
        loans_result = await session.execute(
            select(func.count(Loan.id)).where(Loan.lender_id == str(lender.id))
        )
        loans_count = loans_result.scalar() or 0

        portfolio_result = await session.execute(
            select(func.sum(Loan.total_amount)).where(Loan.lender_id == str(lender.id))
        )
        portfolio = float(portfolio_result.scalar() or 0)

        items.append(
            {
                "id": str(lender.id),
                "legal_name": lender.legal_name,
                "commercial_name": lender.commercial_name,
                "status": lender.status.value
                if hasattr(lender.status, "value")
                else str(lender.status),
                "plan": lender.subscription_plan or "basic",
                "loans_count": loans_count,
                "portfolio_amount": portfolio,
            }
        )

    return {"lenders": items, "total": total, "skip": skip, "limit": limit}
