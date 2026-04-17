"""Subscriptions API - SaaS subscription management."""

from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.dependencies import get_current_user, require_roles
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.core.exceptions import AppException


router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/current")
async def get_current_subscription(
    current_user: User = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get current lender subscription."""
    result = await session.execute(
        select(Subscription).where(Subscription.lender_id == current_user.lender_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    return {
        "subscription_id": str(subscription.id),
        "status": subscription.status.value
        if hasattr(subscription.status, "value")
        else subscription.status,
        "plan_id": subscription.plan_id,
        "current_period_start": subscription.current_period_start.isoformat()
        if subscription.current_period_start
        else None,
        "current_period_end": subscription.current_period_end.isoformat()
        if subscription.current_period_end
        else None,
        "cancel_at_period_end": subscription.cancel_at_period_end,
    }


@router.post("/create")
async def create_subscription(
    plan_id: str,
    payment_method_nonce: str = "fake_nonce",
    current_user: User = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create new subscription (mock implementation)."""
    subscription = Subscription(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        lender_id=current_user.lender_id,
        plan_id=plan_id,
        status=SubscriptionStatus.TRIAL,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow(),
        cancel_at_period_end=False,
    )
    session.add(subscription)
    await session.commit()

    return {
        "success": True,
        "subscription_id": str(subscription.id),
        "plan_id": plan_id,
        "status": "trial",
        "message": "Subscription created (demo mode)",
    }


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(require_roles("owner")),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel subscription at period end."""
    result = await session.execute(
        select(Subscription).where(Subscription.lender_id == current_user.lender_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found",
        )

    subscription.cancel_at_period_end = True
    await session.commit()
    return {"success": True, "message": "Subscription will be cancelled at period end"}
