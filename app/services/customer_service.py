"""Service for customer business logic - registration, linking, KYC."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CustomerStatus
from app.core.exceptions import ConflictException, ValidationException, NotFoundException
from app.models.customer import Customer
from app.repositories.customer_repo import CustomerRepository


class CustomerService:
    """Service for customer operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.customer_repo = CustomerRepository(session)

    async def create_customer(
        self,
        lender_id: UUID,
        first_name: str,
        last_name: str,
        document_type: str,
        document_number: str,
        phone: str,
        email: str,
        credit_limit: float | None = None,
    ) -> Customer:
        """Create a new customer within a lender scope."""
        email = email.lower().strip()
        document_number = document_number.strip()

        if len(first_name.strip()) < 2:
            raise ValidationException("First name must be at least 2 characters")
        if len(last_name.strip()) < 2:
            raise ValidationException("Last name must be at least 2 characters")
        if await self.customer_repo.email_exists(email):
            raise ConflictException("Email already in use by another customer")
        if await self.customer_repo.document_exists(document_number):
            raise ConflictException("Document number already in use")

        customer = await self.customer_repo.create({
            "lender_id": lender_id,
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "document_type": document_type.strip(),
            "document_number": document_number,
            "phone": phone.strip(),
            "email": email,
            "status": CustomerStatus.ACTIVE,
            "credit_limit": credit_limit,
        })
        await self.session.flush()
        return customer

    async def get_customer(self, customer_id: UUID) -> Customer:
        """Get customer by ID."""
        return await self.customer_repo.get_or_404(customer_id, error_code="CUSTOMER_NOT_FOUND")

    async def get_customer_by_email(self, email: str) -> Customer:
        """Get customer by email."""
        customer = await self.customer_repo.get_by_email(email)
        if not customer:
            raise NotFoundException("Customer not found", code="CUSTOMER_NOT_FOUND")
        return customer

    async def get_lender_customers(self, lender_id: UUID) -> list[Customer]:
        """Get all customers for a lender."""
        return await self.customer_repo.get_by_lender(lender_id)

    async def update_customer_profile(
        self,
        customer_id: UUID,
        **kwargs,
    ) -> Customer:
        """Update customer profile with new data (phone, address, etc)."""
        customer = await self.get_customer(customer_id)

        # Validate if updating email
        if "email" in kwargs:
            new_email = kwargs["email"].lower().strip()
            if new_email != customer.email:
                existing = await self.customer_repo.get_by_email(new_email)
                if existing:
                    raise ConflictException("Email already in use by another customer")
                kwargs["email"] = new_email

        # Validate if updating document
        if "document_number" in kwargs:
            new_doc = kwargs["document_number"].strip()
            if new_doc != customer.document_number:
                if await self.customer_repo.document_exists(new_doc, exclude_id=customer_id):
                    raise ConflictException("Document number already in use")
                kwargs["document_number"] = new_doc

        await self.customer_repo.update(customer, kwargs)
        await self.session.flush()
        return customer

    async def set_credit_limit(self, customer_id: UUID, credit_limit: float) -> Customer:
        """Set customer credit limit."""
        if credit_limit < 0:
            raise ValidationException("Credit limit must be positive")

        customer = await self.get_customer(customer_id)
        customer.credit_limit = credit_limit
        await self.session.flush()
        return customer

    async def get_customer_loans(self, customer_id: UUID):
        """Get all loans for a customer (requires Loan model)."""
        # TODO: Implement when Loan model is ready
        return []

    async def get_customer_payments(self, customer_id: UUID):
        """Get all payments for a customer (requires Payment model)."""
        # TODO: Implement when Payment model is ready
        return []

    async def activate_customer(self, customer_id: UUID) -> Customer:
        """Activate a customer."""
        customer = await self.get_customer(customer_id)

        if customer.status == CustomerStatus.ACTIVE:
            raise ValidationException("Customer is already active")

        customer.status = CustomerStatus.ACTIVE
        await self.session.flush()
        return customer

    async def block_customer(self, customer_id: UUID, reason: str | None = None) -> Customer:
        """Block a customer (e.g., due to fraud)."""
        customer = await self.get_customer(customer_id)

        if customer.status == CustomerStatus.BLOCKED:
            raise ValidationException("Customer is already blocked")

        customer.status = CustomerStatus.BLOCKED
        await self.session.flush()
        return customer

    async def get_customer_summary(self, customer_id: UUID) -> dict:
        """Get customer summary with loans and payments."""
        customer = await self.get_customer(customer_id)

        loans = await self.get_customer_loans(customer_id)
        payments = await self.get_customer_payments(customer_id)

        return {
            "id": str(customer.id),
            "email": customer.email,
            "name": f"{customer.first_name} {customer.last_name}",
            "status": customer.status.value,
            "credit_limit": float(customer.credit_limit or 0),
            "total_loans": len(loans),
            "total_payments": len(payments),
            "created_at": customer.created_at.isoformat(),
        }
