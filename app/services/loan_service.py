"""Loan service - create loans and manage disbursement."""

from uuid import uuid4
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.loan_repo import LoanRepository, InstallmentRepository, DisbursementRepository
from app.repositories.loan_application_repo import LoanApplicationRepository
from app.repositories.customer_repo import CustomerRepository
from app.models.loan import Loan, Installment, Disbursement, LoanStatus, InstallmentStatus, DisbursementStatus
from app.models.loan_application import LoanApplicationStatus
from app.core.exceptions import ValidationException, NotFoundException, ForbiddenException
from app.core.utils import generate_installment_schedule


class LoanService:
    """Service for loan creation and management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.loan_repo = LoanRepository(session)
        self.installment_repo = InstallmentRepository(session)
        self.disbursement_repo = DisbursementRepository(session)
        self.application_repo = LoanApplicationRepository(session)
        self.customer_repo = CustomerRepository(session)

    async def create_loan_from_application(
        self,
        application_id: str,
        lender_id: str,
        approved_by_user_id: str,
        first_due_date: date,
        internal_notes: str = None,
    ) -> dict:
        """Create loan from approved application."""
        # Get application
        application = await self.application_repo.get_or_404(application_id)

        if application.lender_id != lender_id:
            raise ForbiddenException("Not authorized to create loan from this application")

        if application.status != LoanApplicationStatus.APPROVED:
            raise ValidationException(f"Application must be approved, current status: {application.status}")

        # Check application hasn't been used already
        existing_loan = await self.loan_repo.get_by_application_id(application_id)
        if existing_loan:
            raise ValidationException("Loan already exists for this application")

        # Generate loan number
        loan_number = self._generate_loan_number(lender_id)

        # Calculate interest
        principal = application.requested_amount
        interest_rate = application.requested_interest_rate
        installments_count = application.requested_installments_count
        frequency = application.requested_frequency

        total_interest = self._calculate_simple_interest(
            principal=principal,
            rate=interest_rate,
            months=self._frequency_to_months(frequency, installments_count),
        )
        total_amount = principal + total_interest

        # Create loan
        loan = await self.loan_repo.create({
            "lender_id": lender_id,
            "customer_id": application.customer_id,
            "loan_application_id": application_id,
            "loan_number": loan_number,
            "principal_amount": principal,
            "interest_rate": interest_rate,
            "interest_type": "fixed",
            "total_interest_amount": total_interest,
            "total_amount": total_amount,
            "installments_count": installments_count,
            "frequency": frequency,
            "first_due_date": first_due_date,
            "status": LoanStatus.APPROVED,
            "approved_by": approved_by_user_id,
            "approved_at": datetime.now(timezone.utc),
            "internal_notes": internal_notes,
        })

        # Generate installment schedule
        await self._generate_installments(
            loan=loan,
            principal=principal,
            total_interest=total_interest,
            installments_count=installments_count,
            frequency=frequency,
            first_due_date=first_due_date,
        )

        await self.session.commit()

        return {
            "loan_id": str(loan.id),
            "loan_number": loan_number,
            "principal": float(principal),
            "total_interest": float(total_interest),
            "total_amount": float(total_amount),
            "installments_count": installments_count,
            "status": loan.status.value,
            "message": "Loan created successfully",
        }

    async def _generate_installments(
        self,
        loan: Loan,
        principal: Decimal,
        total_interest: Decimal,
        installments_count: int,
        frequency: str,
        first_due_date: date,
    ) -> None:
        """Generate installment schedule."""
        schedule = generate_installment_schedule(
            principal=float(principal),
            total_interest=float(total_interest),
            installments_count=installments_count,
            frequency=frequency,
            start_date=first_due_date,
        )

        for installment_data in schedule:
            await self.installment_repo.create({
                "loan_id": loan.id,
                "installment_number": installment_data["number"],
                "due_date": installment_data["due_date"],
                "principal_component": Decimal(str(installment_data["principal"])),
                "interest_component": Decimal(str(installment_data["interest"])),
                "amount_due": Decimal(str(installment_data["amount"])),
                "status": InstallmentStatus.PENDING,
            })

    async def create_disbursement(
        self,
        loan_id: str,
        lender_id: str,
        amount: Decimal,
        method: str,
        created_by_user_id: str,
        bank_name: str = None,
        reference_number: str = None,
        receipt_url: str = None,
    ) -> dict:
        """Create disbursement for loan."""
        loan = await self.loan_repo.get_or_404(loan_id)

        if loan.lender_id != lender_id:
            raise ForbiddenException("Not authorized to disburse this loan")

        # Validate loan status
        if loan.status not in (LoanStatus.APPROVED, LoanStatus.DISBURSED):
            raise ValidationException(f"Cannot disburse loan with status {loan.status}")

        # Validate amount
        if amount <= 0 or amount > loan.principal_amount:
            raise ValidationException("Disbursement amount invalid")

        # Check if already disbursed
        existing = await self.disbursement_repo.get_completed_for_loan(loan_id)
        if existing:
            raise ValidationException("Loan already has a completed disbursement")

        # Create disbursement
        disbursement = await self.disbursement_repo.create({
            "loan_id": loan_id,
            "amount": amount,
            "method": method,
            "bank_name": bank_name,
            "reference_number": reference_number,
            "receipt_url": receipt_url,
            "status": DisbursementStatus.COMPLETED,
            "created_by": created_by_user_id,
            "disbursed_at": datetime.utcnow(),
        })

        # Update loan status
        loan.status = LoanStatus.ACTIVE
        loan.disbursement_date = date.today()
        await self.loan_repo.update(loan, {
            "status": LoanStatus.ACTIVE,
            "disbursement_date": date.today(),
        })

        await self.session.commit()

        return {
            "disbursement_id": str(disbursement.id),
            "loan_id": str(loan_id),
            "amount": float(amount),
            "method": method,
            "status": disbursement.status.value,
            "message": "Disbursement completed",
        }

    async def get_loan(self, loan_id: str, lender_id: str) -> dict:
        """Get loan details with installment schedule."""
        loan = await self.loan_repo.get_or_404(loan_id)

        if loan.lender_id != lender_id:
            raise ForbiddenException("Not authorized to view this loan")

        installments = await self.installment_repo.get_by_loan(loan_id)
        customer = await self.customer_repo.get_or_404(loan.customer_id)
        balance = loan.total_amount - sum(inst.amount_paid for inst in installments)

        return {
            "loan_id": str(loan.id),
            "loan_number": loan.loan_number,
            "customer_id": str(loan.customer_id),
            "customer_name": f"{customer.first_name} {customer.last_name}".strip(),
            "principal": float(loan.principal_amount),
            "interest_rate": float(loan.interest_rate),
            "total_interest": float(loan.total_interest_amount),
            "total_amount": float(loan.total_amount),
            "balance": float(balance),
            "frequency": loan.frequency,
            "status": loan.status.value,
            "first_due_date": loan.first_due_date.isoformat(),
            "disbursement_date": loan.disbursement_date.isoformat() if loan.disbursement_date else None,
            "installments": [
                {
                    "number": inst.installment_number,
                    "due_date": inst.due_date.isoformat(),
                    "amount": float(inst.amount_due),
                    "paid": float(inst.amount_paid),
                    "status": inst.status.value,
                }
                for inst in installments
            ],
            "created_at": loan.created_at.isoformat(),
        }

    async def list_loans(self, lender_id: str, status: str | None = None) -> dict:
        """List loans for a lender with customer summary."""
        status_enum = LoanStatus(status) if status else None
        loans = await self.loan_repo.get_by_lender(lender_id, status_enum)

        items = []
        for loan in loans:
            installments = await self.installment_repo.get_by_loan(loan.id)
            customer = await self.customer_repo.get_or_404(loan.customer_id)
            balance = loan.total_amount - sum(inst.amount_paid for inst in installments)
            items.append(
                {
                    "loan_id": str(loan.id),
                    "loan_number": loan.loan_number,
                    "customer_id": str(loan.customer_id),
                    "customer_name": f"{customer.first_name} {customer.last_name}".strip(),
                    "principal": float(loan.principal_amount),
                    "interest_rate": float(loan.interest_rate),
                    "total_amount": float(loan.total_amount),
                    "balance": float(balance),
                    "status": loan.status.value,
                    "created_at": loan.created_at.isoformat(),
                }
            )

        return {
            "count": len(items),
            "loans": items,
        }

    def _generate_loan_number(self, lender_id: str) -> str:
        """Generate unique loan number."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = str(uuid4())[:8].upper()
        return f"LN-{lender_id[:4].upper()}-{timestamp}-{random_suffix}"

    def _calculate_simple_interest(self, principal: Decimal, rate: Decimal, months: float) -> Decimal:
        """Calculate simple interest: I = P * R * T / 100."""
        if not isinstance(principal, Decimal):
            principal = Decimal(str(principal))
        if not isinstance(rate, Decimal):
            rate = Decimal(str(rate))

        return principal * rate * Decimal(str(months)) / Decimal("1200")

    def _frequency_to_months(self, frequency: str, count: int) -> float:
        """Convert frequency and count to months."""
        freq_map = {
            "weekly": 7 / 30,
            "biweekly": 14 / 30,
            "monthly": 1,
        }
        return freq_map.get(frequency, 1) * count
