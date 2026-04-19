"""Lender settings API - company info, subscription, account management."""

from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.dependencies import get_current_user, get_lender_context, require_roles
from app.models.user import User
from app.models.lender import Lender, LenderBankAccount
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.user_repo import UserRepository


router = APIRouter(prefix="/lender/settings", tags=["lender-settings"])


class LenderCompanyInfo(BaseModel):
    legal_name: str
    commercial_name: str | None = None
    document_type: str
    document_number: str
    email: str
    phone: str


class UpdateLenderCompanyRequest(BaseModel):
    legal_name: str | None = None
    commercial_name: str | None = None
    document_type: str | None = None
    document_number: str | None = None
    email: str | None = None
    phone: str | None = None


class SubscriptionInfo(BaseModel):
    subscription_id: str | None = None
    plan_id: str | None = None
    status: str
    current_period_start: str | None = None
    current_period_end: str | None = None
    cancel_at_period_end: bool = False


class LenderSettingsResponse(BaseModel):
    company: LenderCompanyInfo
    subscription: SubscriptionInfo


@router.get("", response_model=LenderSettingsResponse)
async def get_lender_settings(
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> LenderSettingsResponse:
    """Get lender settings including company info and subscription."""
    lender_result = await session.execute(select(Lender).where(Lender.id == lender_id))
    lender = lender_result.scalar_one_or_none()

    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")

    subscription_result = await session.execute(
        select(Subscription).where(Subscription.lender_id == lender_id)
    )
    subscription = subscription_result.scalar_one_or_none()

    company = LenderCompanyInfo(
        legal_name=lender.legal_name,
        commercial_name=lender.commercial_name,
        document_type=lender.document_type,
        document_number=lender.document_number,
        email=lender.email,
        phone=lender.phone,
    )

    sub_info = SubscriptionInfo(
        status="none",
        cancel_at_period_end=False,
    )
    if subscription:
        sub_info = SubscriptionInfo(
            subscription_id=str(subscription.id),
            plan_id=subscription.plan_id,
            status=subscription.status.value
            if hasattr(subscription.status, "value")
            else subscription.status,
            current_period_start=subscription.current_period_start.isoformat()
            if subscription.current_period_start
            else None,
            current_period_end=subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None,
            cancel_at_period_end=subscription.cancel_at_period_end,
        )

    return LenderSettingsResponse(company=company, subscription=sub_info)


@router.put("")
async def update_lender_settings(
    request: UpdateLenderCompanyRequest,
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Update lender company information."""
    lender_result = await session.execute(select(Lender).where(Lender.id == lender_id))
    lender = lender_result.scalar_one_or_none()

    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(lender, field, value)

    lender.updated_at = datetime.utcnow()
    await session.commit()

    return {"success": True, "message": "Company information updated"}


@router.get("/subscription", response_model=SubscriptionInfo)
async def get_subscription(
    current_user: User = Depends(require_roles("owner")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionInfo:
    """Get lender subscription details."""
    result = await session.execute(
        select(Subscription).where(Subscription.lender_id == lender_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return SubscriptionInfo(status="none", cancel_at_period_end=False)

    return SubscriptionInfo(
        subscription_id=str(subscription.id),
        plan_id=subscription.plan_id,
        status=subscription.status.value
        if hasattr(subscription.status, "value")
        else subscription.status,
        current_period_start=subscription.current_period_start.isoformat()
        if subscription.current_period_start
        else None,
        current_period_end=subscription.current_period_end.isoformat()
        if subscription.current_period_end
        else None,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )


@router.post("/subscription")
async def create_or_update_subscription(
    plan_id: str,
    current_user: User = Depends(require_roles("owner")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create or update subscription (mock implementation)."""
    result = await session.execute(
        select(Subscription).where(Subscription.lender_id == lender_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.plan_id = plan_id
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.current_period_start = datetime.utcnow()
        subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
        subscription.cancel_at_period_end = False
    else:
        subscription = Subscription(
            lender_id=lender_id,
            plan_id=plan_id,
            status=SubscriptionStatus.TRIAL,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30),
            cancel_at_period_end=False,
        )
        session.add(subscription)

    await session.commit()

    return {
        "success": True,
        "subscription_id": str(subscription.id),
        "plan_id": plan_id,
        "status": "active",
    }


@router.post("/subscription/cancel")
async def cancel_subscription(
    current_user: User = Depends(require_roles("owner")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel subscription at end of billing period."""
    result = await session.execute(
        select(Subscription).where(Subscription.lender_id == lender_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    subscription.cancel_at_period_end = True
    await session.commit()

    return {"success": True, "message": "Subscription will be cancelled at period end"}


@router.delete("/account")
async def delete_lender_account(
    current_user: User = Depends(require_roles("owner")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete lender account and all associated data (irreversible)."""
    lender_result = await session.execute(select(Lender).where(Lender.id == lender_id))
    lender = lender_result.scalar_one_or_none()

    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")

    lender.status = "cancelled"
    lender.updated_at = datetime.utcnow()
    await session.commit()

    return {"success": True, "message": "Account scheduled for deletion"}


# === Bank Accounts ===


class LenderBankAccountResponse(BaseModel):
    id: str
    bank_name: str
    account_type: str
    account_number_masked: str
    account_holder_name: str
    currency: str
    is_primary: bool
    status: str
    created_at: str


class CreateLenderBankAccountRequest(BaseModel):
    bank_name: str
    account_type: str
    account_number: str
    account_holder_name: str
    currency: str = "DOP"
    is_primary: bool = False


def mask_account_number(number: str) -> str:
    """Mask all but last 4 digits."""
    if len(number) <= 4:
        return number
    return "*" * (len(number) - 4) + number[-4:]


@router.get("/accounts")
async def list_lender_accounts(
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List all bank accounts for the lender."""
    result = await session.execute(
        select(LenderBankAccount)
        .where(LenderBankAccount.lender_id == lender_id)
        .order_by(
            LenderBankAccount.is_primary.desc(), LenderBankAccount.created_at.desc()
        )
    )
    accounts = result.scalars().all()

    return {
        "accounts": [
            {
                "id": str(acc.id),
                "bank_name": acc.bank_name,
                "account_type": acc.account_type,
                "account_number_masked": acc.account_number_masked,
                "account_holder_name": acc.account_holder_name,
                "currency": acc.currency,
                "is_primary": acc.is_primary,
                "status": acc.status,
                "created_at": acc.created_at.isoformat(),
            }
            for acc in accounts
        ]
    }


@router.post("/accounts", response_model=LenderBankAccountResponse)
async def create_lender_bank_account(
    request: CreateLenderBankAccountRequest,
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> LenderBankAccountResponse:
    """Create a new bank account for the lender."""
    existing_accounts_result = await session.execute(
        select(LenderBankAccount).where(
            LenderBankAccount.lender_id == lender_id,
            LenderBankAccount.status != "deleted",
        )
    )
    existing_accounts = existing_accounts_result.scalars().all()
    has_primary = any(acc.is_primary for acc in existing_accounts)

    should_be_primary = request.is_primary or not has_primary
    if should_be_primary:
        for acc in existing_accounts:
            if acc.is_primary:
                acc.is_primary = False

    account = LenderBankAccount(
        lender_id=lender_id,
        bank_name=request.bank_name,
        account_type=request.account_type,
        account_number_masked=request.account_number.strip(),
        account_holder_name=request.account_holder_name,
        currency=request.currency,
        is_primary=should_be_primary,
        status="active",
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)

    return LenderBankAccountResponse(
        id=str(account.id),
        bank_name=account.bank_name,
        account_type=account.account_type,
        account_number_masked=account.account_number_masked,
        account_holder_name=account.account_holder_name,
        currency=account.currency,
        is_primary=account.is_primary,
        status=account.status,
        created_at=account.created_at.isoformat(),
    )


@router.delete("/accounts/{account_id}")
async def delete_lender_bank_account(
    account_id: str,
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a lender bank account."""
    result = await session.execute(
        select(LenderBankAccount).where(
            LenderBankAccount.id == account_id,
            LenderBankAccount.lender_id == lender_id,
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.status = "deleted"
    account.updated_at = datetime.utcnow()
    await session.commit()

    return {"success": True, "message": "Account deleted"}


@router.put("/accounts/{account_id}/primary")
async def set_lender_primary_account(
    account_id: str,
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Set a bank account as primary."""
    result = await session.execute(
        select(LenderBankAccount).where(
            LenderBankAccount.id == account_id,
            LenderBankAccount.lender_id == lender_id,
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    result_all = await session.execute(
        select(LenderBankAccount).where(
            LenderBankAccount.lender_id == lender_id,
            LenderBankAccount.is_primary == True,
        )
    )
    for acc in result_all.scalars().all():
        acc.is_primary = False

    account.is_primary = True
    account.updated_at = datetime.utcnow()
    await session.commit()

    return {"success": True, "message": "Primary account updated"}
