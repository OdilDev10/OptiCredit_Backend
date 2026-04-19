"""Lender settings API - company info, subscription, account management, documents."""

from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.dependencies import get_current_user, get_lender_context, require_roles
from app.models.user import User
from app.models.lender import Lender, LenderBankAccount
from app.models.loan import Loan
from app.models.lender_document import LenderDocument
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.user_repo import UserRepository
from app.core.enums import LenderDocumentType, LenderStatus, LoanStatus, UserStatus
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.services.storage_service import storage_service


router = APIRouter(prefix="/lender/settings", tags=["lender-settings"])


class LenderCompanyInfo(BaseModel):
    legal_name: str
    commercial_name: str | None = None
    document_type: str
    document_number: str
    email: str
    phone: str
    address_line: str | None = None


class UpdateLenderCompanyRequest(BaseModel):
    legal_name: str | None = None
    commercial_name: str | None = None
    document_type: str | None = None
    document_number: str | None = None
    email: str | None = None
    phone: str | None = None
    address_line: str | None = None


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
        address_line=lender.address_line,
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
    """Schedule lender account deletion after business-rule checks."""
    lender_result = await session.execute(select(Lender).where(Lender.id == lender_id))
    lender = lender_result.scalar_one_or_none()

    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")

    active_loans_query = select(func.count(Loan.id)).where(
        Loan.lender_id == lender.id,
        Loan.status.in_(
            [
                LoanStatus.APPROVED,
                LoanStatus.DISBURSED,
                LoanStatus.ACTIVE,
                LoanStatus.OVERDUE,
            ]
        ),
    )
    active_loans = await session.scalar(active_loans_query)
    if active_loans and active_loans > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ACCOUNT_DELETION_BLOCKED_ACTIVE_LOANS",
                "message": "No puedes eliminar la cuenta del prestamista con préstamos activos.",
                "detail": {
                    "active_loans": int(active_loans),
                },
            },
        )

    now = datetime.utcnow()
    scheduled_deletion_at = now + timedelta(days=30)

    lender.status = LenderStatus.SUSPENDED
    lender.updated_at = now

    lender_users_result = await session.execute(select(User).where(User.lender_id == lender.id))
    lender_users = lender_users_result.scalars().all()
    for lender_user in lender_users:
        lender_user.status = UserStatus.INACTIVE
        lender_user.updated_at = now

    await AuthService(session).logout_all(str(current_user.id))
    await AuditService(session).log(
        action="delete",
        resource_type="lender_account",
        resource_id=str(lender.id),
        description="Lender account scheduled for deletion in 30 days",
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=f"{current_user.first_name} {current_user.last_name}",
        lender_id=lender.id,
        metadata={
            "requested_at": now.isoformat(),
            "scheduled_deletion_at": scheduled_deletion_at.isoformat(),
            "retention_policy": "soft-delete-audit-retention",
        },
    )

    await session.commit()

    return {
        "success": True,
        "message": "Cuenta del prestamista programada para eliminación en 30 días",
        "scheduled_deletion_at": scheduled_deletion_at.isoformat(),
        "retention_policy": "soft-delete-audit-retention",
    }


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


# === Legal Documents ===

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}


class LenderDocumentResponse(BaseModel):
    id: str
    document_type: str
    file_name: str
    file_size: int | None
    mime_type: str | None
    status: str
    created_at: str


class LenderDocumentsResponse(BaseModel):
    documents: list[LenderDocumentResponse]


@router.get("/documents", response_model=LenderDocumentsResponse)
async def list_lender_documents(
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> LenderDocumentsResponse:
    """List all legal documents for the lender."""
    result = await session.execute(
        select(LenderDocument)
        .where(LenderDocument.lender_id == lender_id)
        .order_by(LenderDocument.created_at.desc())
    )
    documents = result.scalars().all()

    return LenderDocumentsResponse(
        documents=[
            LenderDocumentResponse(
                id=str(doc.id),
                document_type=doc.document_type,
                file_name=doc.file_name,
                file_size=doc.file_size,
                mime_type=doc.mime_type,
                status=doc.status,
                created_at=doc.created_at.isoformat(),
            )
            for doc in documents
        ]
    )


@router.post("/documents", response_model=LenderDocumentResponse)
async def upload_lender_document(
    document_type: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> LenderDocumentResponse:
    """Upload a legal document for the lender (RNC, license, etc.)."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    ext = "." + file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    file_content = await file.read()
    file_size = len(file_content)

    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = await storage_service.upload(
        file_content,
        unique_name,
        folder="lender_documents",
    )

    document = LenderDocument(
        lender_id=lender_id,
        document_type=document_type,
        file_name=file.filename or unique_name,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        status="pending",
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    return LenderDocumentResponse(
        id=str(document.id),
        document_type=document.document_type,
        file_name=document.file_name,
        file_size=document.file_size,
        mime_type=document.mime_type,
        status=document.status,
        created_at=document.created_at.isoformat(),
    )


@router.delete("/documents/{document_id}")
async def delete_lender_document(
    document_id: str,
    current_user: User = Depends(require_roles("owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a lender document."""
    result = await session.execute(
        select(LenderDocument).where(
            LenderDocument.id == document_id,
            LenderDocument.lender_id == lender_id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        await storage_service.delete(document.file_path)
    except Exception:
        pass

    await session.delete(document)
    await session.commit()

    return {"success": True, "message": "Document deleted"}
