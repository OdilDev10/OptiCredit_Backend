"""Loan management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.loan_service import LoanService
from app.core.exceptions import AppException

router = APIRouter(prefix="/loans", tags=["loans"])


class CreateLoanRequest(BaseModel):
    """Create loan from application request."""
    application_id: str
    first_due_date: date
    internal_notes: str | None = None


class DisbursementRequest(BaseModel):
    """Disbursement request."""
    amount: Decimal = Field(..., gt=0)
    method: str
    bank_name: str | None = None
    reference_number: str | None = None
    receipt_url: str | None = None


class LoanResponse(BaseModel):
    """Loan response."""
    loan_id: str
    loan_number: str
    principal: float
    status: str


@router.post("/", response_model=LoanResponse)
async def create_loan(
    request: CreateLoanRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create loan from approved application."""
    try:
        service = LoanService(session)
        result = await service.create_loan_from_application(
            request.application_id,
            current_user.lender_id,
            current_user.id,
            request.first_due_date,
            request.internal_notes,
        )
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/")
async def list_loans(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List loans for the authenticated lender."""
    try:
        service = LoanService(session)
        result = await service.list_loans(current_user.lender_id, status)
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{loan_id}")
async def get_loan(
    loan_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Get loan details with installment schedule."""
    try:
        service = LoanService(session)
        result = await service.get_loan(loan_id, current_user.lender_id)
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{loan_id}/disburse")
async def create_disbursement(
    loan_id: str,
    request: DisbursementRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Create disbursement for loan."""
    try:
        service = LoanService(session)
        result = await service.create_disbursement(
            loan_id,
            current_user.lender_id,
            request.amount,
            request.method,
            current_user.id,
            request.bank_name,
            request.reference_number,
            request.receipt_url,
        )
        return result
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
