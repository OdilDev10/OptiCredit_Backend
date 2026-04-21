"""Admin platform API - lender management with pagination and search."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_roles
from app.models.user import User
from app.models.lender import Lender, LenderStatus
from app.models.loan import Loan
from app.models.customer import Customer
from app.schemas.admin import (
    AdminLenderCard,
    AdminLenderKPIs,
    PaginatedAdminLendersResponse,
)


router = APIRouter(prefix="/admin/lenders", tags=["admin"])


@router.get("", response_model=PaginatedAdminLendersResponse)
async def list_lenders_admin(
    search: str | None = Query(default=None),
    lender_type: str | None = Query(default=None),
    plan: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> PaginatedAdminLendersResponse:
    """List all lenders for admin with pagination and search."""
    query = select(Lender)
    count_query = select(func.count(Lender.id))

    if search:
        search_filter = or_(
            Lender.legal_name.ilike(f"%{search}%"),
            Lender.commercial_name.ilike(f"%{search}%"),
            Lender.document_number.ilike(f"%{search}%"),
            Lender.email.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if lender_type:
        query = query.where(Lender.lender_type == lender_type)
        count_query = count_query.where(Lender.lender_type == lender_type)

    if plan:
        query = query.where(Lender.subscription_plan == plan)
        count_query = count_query.where(Lender.subscription_plan == plan)

    if status_filter:
        query = query.where(Lender.status == status_filter)
        count_query = count_query.where(Lender.status == status_filter)

    # Total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Paginated results
    query = query.order_by(desc(Lender.created_at)).offset(skip).limit(limit)
    result = await session.execute(query)
    lenders = result.scalars().all()

    items = []
    for lender in lenders:
        # Count clients
        clients_result = await session.execute(
            select(func.count(Customer.id)).where(Customer.lender_id == str(lender.id))
        )
        clients_count = clients_result.scalar() or 0

        # Count loans
        loans_result = await session.execute(
            select(func.count(Loan.id)).where(Loan.lender_id == str(lender.id))
        )
        loans_count = loans_result.scalar() or 0

        # Sum portfolio
        portfolio_result = await session.execute(
            select(func.sum(Loan.total_amount)).where(Loan.lender_id == str(lender.id))
        )
        portfolio_amount = portfolio_result.scalar() or 0

        items.append(
            AdminLenderCard(
                id=str(lender.id),
                legal_name=lender.legal_name,
                commercial_name=lender.commercial_name,
                lender_type=lender.lender_type.value
                if hasattr(lender.lender_type, "value")
                else str(lender.lender_type),
                document_type=lender.document_type,
                document_number=lender.document_number,
                status=lender.status.value
                if hasattr(lender.status, "value")
                else str(lender.status),
                plan=lender.subscription_plan or "basic",
                clients_count=clients_count,
                loans_count=loans_count,
                portfolio_amount=float(portfolio_amount) if portfolio_amount else 0.0,
                registered_at=lender.created_at,
                reviewed_at=lender.updated_at
                if lender.status == LenderStatus.ACTIVE
                else None,
                suspended_at=None,
            )
        )

    return PaginatedAdminLendersResponse(
        items=items, total=total, skip=skip, limit=limit
    )


@router.get("/kpis", response_model=AdminLenderKPIs)
async def get_admin_lender_kpis(
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> AdminLenderKPIs:
    """Get admin dashboard KPIs for lenders."""
    result = await session.execute(select(func.count(Lender.id)))
    total = result.scalar() or 0

    result = await session.execute(
        select(func.count(Lender.id)).where(Lender.status == LenderStatus.ACTIVE)
    )
    active = result.scalar() or 0

    result = await session.execute(
        select(func.count(Lender.id)).where(Lender.status == LenderStatus.PENDING)
    )
    in_review = result.scalar() or 0

    result = await session.execute(
        select(func.count(Lender.id)).where(Lender.status == LenderStatus.SUSPENDED)
    )
    suspended = result.scalar() or 0

    return AdminLenderKPIs(
        total_entities=total,
        active_count=active,
        in_review_count=in_review,
        suspended_count=suspended,
    )


@router.post("/{lender_id}/approve", status_code=status.HTTP_200_OK)
async def approve_lender(
    lender_id: str,
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Approve a lender (change status to active)."""
    result = await session.execute(select(Lender).where(Lender.id == lender_id))
    lender = result.scalar_one_or_none()
    if not lender:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Lender not found")

    lender.status = LenderStatus.ACTIVE
    await session.commit()
    return {"message": "Lender approved successfully"}


@router.post("/{lender_id}/suspend", status_code=status.HTTP_200_OK)
async def suspend_lender(
    lender_id: str,
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Suspend a lender."""
    result = await session.execute(select(Lender).where(Lender.id == lender_id))
    lender = result.scalar_one_or_none()
    if not lender:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Lender not found")

    lender.status = LenderStatus.SUSPENDED
    await session.commit()
    return {"message": "Lender suspended successfully"}


@router.post("/{lender_id}/reactivate", status_code=status.HTTP_200_OK)
async def reactivate_lender(
    lender_id: str,
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Reactivate a suspended lender."""
    result = await session.execute(select(Lender).where(Lender.id == lender_id))
    lender = result.scalar_one_or_none()
    if not lender:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Lender not found")

    lender.status = LenderStatus.ACTIVE
    await session.commit()
    return {"message": "Lender reactivated successfully"}


class RejectLenderRequest(BaseModel):
    reason: str = Field(..., description="Reason for rejection")


@router.get("/pending-applications", response_model=dict)
async def list_pending_applications(
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List all pending lender registration applications."""
    result = await session.execute(
        select(Lender).where(Lender.status == LenderStatus.PENDING)
    )
    lenders = result.scalars().all()
    items = []
    for lender in lenders:
        items.append(
            {
                "id": str(lender.id),
                "legal_name": lender.legal_name,
                "commercial_name": lender.commercial_name,
                "lender_type": lender.lender_type.value
                if hasattr(lender.lender_type, "value")
                else str(lender.lender_type),
                "document_type": lender.document_type,
                "document_number": lender.document_number,
                "email": lender.email,
                "phone": lender.phone,
                "status": lender.status.value
                if hasattr(lender.status, "value")
                else str(lender.status),
                "rejection_reason": None,
                "submitted_at": lender.created_at.isoformat()
                if lender.created_at
                else None,
            }
        )
    return {"items": items}


@router.post("/{lender_id}/reject", status_code=status.HTTP_200_OK)
async def reject_lender(
    lender_id: str,
    request: RejectLenderRequest,
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a lender application with a reason."""
    result = await session.execute(select(Lender).where(Lender.id == lender_id))
    lender = result.scalar_one_or_none()
    if not lender:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("Lender not found")

    lender.status = LenderStatus.REJECTED
    await session.commit()
    return {"message": f"Lender rejected: {request.reason}"}


# Admin Users endpoints
@router.get("/users", tags=["admin"])
async def list_admin_users(
    search: str | None = Query(default=None),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List all users for admin with pagination and search."""
    from app.repositories.user_repo import UserRepository
    from app.models.user import User as UserModel
    from pydantic import BaseModel

    class UserCard(BaseModel):
        id: str
        email: str
        first_name: str
        last_name: str
        role: str
        account_type: str
        status: str
        lender_id: str | None
        lender_name: str | None
        created_at: datetime

    class PaginatedUsersResponse(BaseModel):
        items: list[UserCard]
        total: int
        skip: int
        limit: int

    repo = UserRepository(session)

    # Build base query
    query = select(UserModel)
    count_query = select(func.count(UserModel.id))

    if search:
        search_filter = or_(
            UserModel.email.ilike(f"%{search}%"),
            UserModel.first_name.ilike(f"%{search}%"),
            UserModel.last_name.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if role:
        query = query.where(UserModel.role == role)
        count_query = count_query.where(UserModel.role == role)

    if status:
        query = query.where(UserModel.status == status)
        count_query = count_query.where(UserModel.status == status)

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Paginated results
    query = query.order_by(desc(UserModel.created_at)).offset(skip).limit(limit)
    result = await session.execute(query)
    users = result.scalars().all()

    items = []
    for user in users:
        lender_name = None
        if user.lender_id:
            lender_result = await session.execute(
                select(Lender.legal_name).where(Lender.id == str(user.lender_id))
            )
            lender_name = lender_result.scalar_one_or_none()

        items.append(
            UserCard(
                id=str(user.id),
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                role=user.role.value if hasattr(user.role, "value") else str(user.role),
                account_type=user.account_type.value
                if hasattr(user.account_type, "value")
                else str(user.account_type),
                status=user.status.value
                if hasattr(user.status, "value")
                else str(user.status),
                lender_id=str(user.lender_id) if user.lender_id else None,
                lender_name=lender_name,
                created_at=user.created_at,
            )
        )

    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/users/kpis", tags=["admin"])
async def get_admin_user_kpis(
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get admin dashboard KPIs for users."""
    from app.repositories.user_repo import UserRepository
    from app.core.enums import UserStatus

    repo = UserRepository(session)

    total_result = await session.execute(select(func.count(User.id)))
    total = total_result.scalar() or 0

    active_result = await session.execute(
        select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
    )
    active = active_result.scalar() or 0

    inactive_result = await session.execute(
        select(func.count(User.id)).where(User.status == UserStatus.INACTIVE)
    )
    inactive = inactive_result.scalar() or 0

    platform_admins_result = await session.execute(
        select(func.count(User.id)).where(User.lender_id == None)
    )
    platform_admins = platform_admins_result.scalar() or 0

    return {
        "total_users": total,
        "active_users": active,
        "inactive_users": inactive,
        "platform_admins": platform_admins,
    }
