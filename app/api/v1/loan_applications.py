"""Loan application endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.loan_application_service import LoanApplicationService
from app.core.exceptions import AppException

router = APIRouter(prefix="/loan-applications", tags=["loan-applications"])


class LoanApplicationCreateRequest(BaseModel):
    """Create loan application request."""
    customer_id: str | None = None
    requested_amount: Decimal = Field(..., gt=0)
    requested_interest_rate: Decimal = Field(..., ge=0)
    requested_installments_count: int = Field(..., gt=0)
    requested_frequency: str
    purpose: str | None = None


class LoanApplicationResponse(BaseModel):
    """Loan application response."""
    application_id: str
    status: str
    requested_amount: float
    requested_interest_rate: float


@router.post("/", response_model=LoanApplicationResponse)
async def create_loan_application(
    request: LoanApplicationCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create new loan application."""
    try:
        service = LoanApplicationService(session)
        customer_id = request.customer_id or str(current_user.id)
        result = await service.create_application(
            customer_id=customer_id,
            lender_id=current_user.lender_id,
            requested_amount=request.requested_amount,
            requested_interest_rate=request.requested_interest_rate,
            requested_installments_count=request.requested_installments_count,
            requested_frequency=request.requested_frequency,
            purpose=request.purpose,
        )
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{application_id}")
async def get_application(
    application_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get loan application details."""
    try:
        service = LoanApplicationService(session)
        result = await service.get_application(application_id, current_user.lender_id)
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/")
async def list_applications(
    status: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List loan applications."""
    try:
        service = LoanApplicationService(session)
        result = await service.list_applications(current_user.lender_id, status, limit)
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{application_id}/approve")
async def approve_application(
    application_id: str,
    review_notes: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Approve loan application."""
    try:
        service = LoanApplicationService(session)
        result = await service.approve_application(
            application_id, current_user.lender_id, current_user.id, review_notes
        )
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{application_id}/reject")
async def reject_application(
    application_id: str,
    review_notes: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Reject loan application."""
    try:
        service = LoanApplicationService(session)
        result = await service.reject_application(
            application_id, current_user.lender_id, current_user.id, review_notes
        )
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
