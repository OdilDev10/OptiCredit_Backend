"""Loan Application service - create and review loan applications."""

from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.loan_application_repo import LoanApplicationRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.lender_repo import LenderRepository
from app.models.loan_application import LoanApplication, LoanApplicationStatus, LoanFrequency
from app.core.exceptions import ValidationException, NotFoundException, ForbiddenException


class LoanApplicationService:
    """Service for loan application operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LoanApplicationRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.lender_repo = LenderRepository(session)

    async def create_application(
        self,
        customer_id: str,
        lender_id: str,
        requested_amount: Decimal,
        requested_interest_rate: Decimal,
        requested_installments_count: int,
        requested_frequency: str,
        purpose: str = None,
    ) -> dict:
        """Create new loan application from customer."""
        # Validate customer exists and is linked to lender
        customer = await self.customer_repo.get_or_404(customer_id)
        if customer.lender_id != lender_id:
            raise ForbiddenException("Customer not linked to this lender")

        # Validate customer status
        if customer.status != "active":
            raise ValidationException(f"Customer status is {customer.status}, must be active")

        # Validate amounts and counts
        if requested_amount <= 0:
            raise ValidationException("Requested amount must be positive")

        if requested_interest_rate < 0:
            raise ValidationException("Interest rate cannot be negative")

        if requested_installments_count <= 0:
            raise ValidationException("Installments count must be positive")

        # Validate frequency
        try:
            LoanFrequency(requested_frequency)
        except ValueError:
            raise ValidationException(f"Invalid frequency: {requested_frequency}")

        # Check customer credit limit
        if requested_amount > customer.credit_limit:
            raise ValidationException(
                f"Requested amount ({requested_amount}) exceeds credit limit ({customer.credit_limit})"
            )

        # Create application
        application = await self.repo.create({
            "customer_id": customer_id,
            "lender_id": lender_id,
            "requested_amount": requested_amount,
            "requested_interest_rate": requested_interest_rate,
            "requested_installments_count": requested_installments_count,
            "requested_frequency": requested_frequency,
            "purpose": purpose,
            "status": LoanApplicationStatus.SUBMITTED,
        })

        await self.session.commit()

        return {
            "application_id": str(application.id),
            "customer_id": str(application.customer_id),
            "requested_amount": float(application.requested_amount),
            "requested_interest_rate": float(application.requested_interest_rate),
            "status": application.status.value,
            "message": "Application submitted successfully",
        }

    async def submit_for_review(self, application_id: str, lender_id: str) -> dict:
        """Submit application for review."""
        application = await self.repo.get_or_404(application_id)

        # Security check
        if application.lender_id != lender_id:
            raise ForbiddenException("Not authorized to review this application")

        # Validate status
        if application.status != LoanApplicationStatus.SUBMITTED:
            raise ValidationException(f"Application status is {application.status}, cannot submit for review")

        # Update status
        application.status = LoanApplicationStatus.UNDER_REVIEW
        await self.repo.update(application, {"status": LoanApplicationStatus.UNDER_REVIEW})
        await self.session.commit()

        return {
            "application_id": str(application.id),
            "status": application.status.value,
            "message": "Application submitted for review",
        }

    async def approve_application(
        self,
        application_id: str,
        lender_id: str,
        reviewed_by_user_id: str,
        review_notes: str = None,
    ) -> dict:
        """Approve loan application."""
        application = await self.repo.get_or_404(application_id)

        # Security checks
        if application.lender_id != lender_id:
            raise ForbiddenException("Not authorized to review this application")

        if application.status not in (LoanApplicationStatus.SUBMITTED, LoanApplicationStatus.UNDER_REVIEW):
            raise ValidationException(f"Cannot approve application with status {application.status}")

        # Update
        application.status = LoanApplicationStatus.APPROVED
        application.reviewed_by = reviewed_by_user_id
        application.reviewed_at = datetime.now(timezone.utc)
        application.review_notes = review_notes

        await self.repo.update(application, {
            "status": LoanApplicationStatus.APPROVED,
            "reviewed_by": reviewed_by_user_id,
            "reviewed_at": datetime.now(timezone.utc),
            "review_notes": review_notes,
        })

        await self.session.commit()

        return {
            "application_id": str(application.id),
            "status": application.status.value,
            "approved_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
            "message": "Application approved",
        }

    async def reject_application(
        self,
        application_id: str,
        lender_id: str,
        reviewed_by_user_id: str,
        review_notes: str,
    ) -> dict:
        """Reject loan application."""
        application = await self.repo.get_or_404(application_id)

        # Security checks
        if application.lender_id != lender_id:
            raise ForbiddenException("Not authorized to review this application")

        if application.status not in (LoanApplicationStatus.SUBMITTED, LoanApplicationStatus.UNDER_REVIEW):
            raise ValidationException(f"Cannot reject application with status {application.status}")

        if not review_notes:
            raise ValidationException("Review notes are required for rejection")

        # Update
        application.status = LoanApplicationStatus.REJECTED
        application.reviewed_by = reviewed_by_user_id
        application.reviewed_at = datetime.now(timezone.utc)
        application.review_notes = review_notes

        await self.repo.update(application, {
            "status": LoanApplicationStatus.REJECTED,
            "reviewed_by": reviewed_by_user_id,
            "reviewed_at": datetime.now(timezone.utc),
            "review_notes": review_notes,
        })

        await self.session.commit()

        return {
            "application_id": str(application.id),
            "status": application.status.value,
            "rejected_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
            "message": "Application rejected",
        }

    async def get_application(self, application_id: str, lender_id: str) -> dict:
        """Get application details."""
        application = await self.repo.get_or_404(application_id)

        if application.lender_id != lender_id:
            raise ForbiddenException("Not authorized to view this application")

        customer = await self.customer_repo.get_or_404(application.customer_id)

        return {
            "application_id": str(application.id),
            "customer_id": str(application.customer_id),
            "customer_name": f"{customer.first_name} {customer.last_name}".strip(),
            "requested_amount": float(application.requested_amount),
            "requested_interest_rate": float(application.requested_interest_rate),
            "requested_installments_count": application.requested_installments_count,
            "requested_frequency": application.requested_frequency,
            "purpose": application.purpose,
            "status": application.status.value,
            "reviewed_by": str(application.reviewed_by) if application.reviewed_by else None,
            "reviewed_at": application.reviewed_at.isoformat() if application.reviewed_at else None,
            "review_notes": application.review_notes,
            "created_at": application.created_at.isoformat(),
        }

    async def list_applications(
        self,
        lender_id: str,
        status: str = None,
        limit: int = 50,
    ) -> dict:
        """List applications for a lender."""
        status_enum = None
        if status:
            try:
                status_enum = LoanApplicationStatus(status)
            except ValueError:
                raise ValidationException(f"Invalid status: {status}")

        applications = await self.repo.get_by_lender(lender_id, status_enum)
        applications = applications[:limit]

        items = []
        for app in applications:
            customer = await self.customer_repo.get_or_404(app.customer_id)
            items.append(
                {
                    "application_id": str(app.id),
                    "customer_id": str(app.customer_id),
                    "customer_name": f"{customer.first_name} {customer.last_name}".strip(),
                    "requested_amount": float(app.requested_amount),
                    "requested_interest_rate": float(app.requested_interest_rate),
                    "requested_installments_count": app.requested_installments_count,
                    "requested_frequency": app.requested_frequency,
                    "purpose": app.purpose,
                    "status": app.status.value,
                    "created_at": app.created_at.isoformat(),
                }
            )

        return {
            "count": len(applications),
            "applications": items,
        }
