"""Unit tests for core services."""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, date

from app.services.loan_application_service import LoanApplicationService
from app.services.loan_service import LoanService
from app.services.payment_service import PaymentService
from app.repositories.loan_application_repo import LoanApplicationRepository
from app.repositories.lender_repo import LenderRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.user_repo import UserRepository
from app.core.exceptions import ValidationException, NotFoundException
from app.models.lender import Lender
from app.models.customer import Customer
from app.models.user import User
from app.core.enums import LenderType, LenderStatus, UserRole, AccountType


@pytest.mark.asyncio
async def test_create_loan_application_valid(db_session):
    """Test creating a valid loan application."""
    # Setup: Create lender, customer, user
    lender = Lender(
        id=uuid4(),
        legal_name="Test Financial",
        commercial_name="TestFinance",
        lender_type=LenderType.FINANCIAL,
        document_type="RNC",
        document_number="123456789",
        email="test@finance.com",
        phone="18093334444",
        status=LenderStatus.ACTIVE,
    )
    db_session.add(lender)

    customer = Customer(
        id=uuid4(),
        lender_id=lender.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="18091234567",
        document_type="Cedula",
        document_number="00100200300",
        status="active",
        credit_limit=Decimal("10000.00"),
    )
    db_session.add(customer)
    await db_session.commit()

    # Test: Create loan application
    service = LoanApplicationService(db_session)
    result = await service.create_application(
        customer_id=str(customer.id),
        lender_id=str(lender.id),
        requested_amount=Decimal("5000.00"),
        requested_interest_rate=Decimal("5.50"),
        requested_installments_count=12,
        requested_frequency="monthly",
        purpose="Personal expenses",
    )

    # Verify
    assert result["status"] == "submitted"
    assert result["requested_amount"] == 5000.0
    assert result["requested_interest_rate"] == 5.5


@pytest.mark.asyncio
async def test_create_loan_application_exceeds_credit_limit(db_session):
    """Test creating a loan application that exceeds credit limit."""
    # Setup
    lender = Lender(
        id=uuid4(),
        legal_name="Test Financial",
        commercial_name="TestFinance",
        lender_type=LenderType.FINANCIAL,
        document_type="RNC",
        document_number="123456789",
        email="test@finance.com",
        phone="18093334444",
        status=LenderStatus.ACTIVE,
    )
    db_session.add(lender)

    customer = Customer(
        id=uuid4(),
        lender_id=lender.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="18091234567",
        document_type="Cedula",
        document_number="00100200300",
        status="active",
        credit_limit=Decimal("2000.00"),  # Low limit
    )
    db_session.add(customer)
    await db_session.commit()

    # Test: Should raise error
    service = LoanApplicationService(db_session)
    with pytest.raises(ValidationException):
        await service.create_application(
            customer_id=str(customer.id),
            lender_id=str(lender.id),
            requested_amount=Decimal("5000.00"),  # Exceeds limit
            requested_interest_rate=Decimal("5.50"),
            requested_installments_count=12,
            requested_frequency="monthly",
        )


@pytest.mark.asyncio
async def test_loan_application_approval(db_session):
    """Test approving a loan application."""
    # Setup
    lender = Lender(
        id=uuid4(),
        legal_name="Test Financial",
        lender_type=LenderType.FINANCIAL,
        document_type="RNC",
        document_number="123456789",
        email="test@finance.com",
        phone="18093334444",
        status=LenderStatus.ACTIVE,
    )
    db_session.add(lender)

    customer = Customer(
        id=uuid4(),
        lender_id=lender.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
        phone="18091234567",
        document_type="Cedula",
        document_number="00100200300",
        status="active",
        credit_limit=Decimal("10000.00"),
    )
    db_session.add(customer)

    reviewer = User(
        id=uuid4(),
        lender_id=lender.id,
        first_name="Manager",
        last_name="User",
        email="manager@finance.com",
        password_hash="hashed",
        role=UserRole.MANAGER,
        account_type=AccountType.INTERNAL,
    )
    db_session.add(reviewer)
    await db_session.commit()

    # Create application
    service = LoanApplicationService(db_session)
    app_result = await service.create_application(
        customer_id=str(customer.id),
        lender_id=str(lender.id),
        requested_amount=Decimal("5000.00"),
        requested_interest_rate=Decimal("5.50"),
        requested_installments_count=12,
        requested_frequency="monthly",
    )

    # Test: Approve it
    approval_result = await service.approve_application(
        application_id=app_result["application_id"],
        lender_id=str(lender.id),
        reviewed_by_user_id=str(reviewer.id),
        review_notes="Approved - good credit profile",
    )

    assert approval_result["status"] == "approved"


@pytest.mark.asyncio
async def test_invalid_loan_frequency(db_session):
    """Test creating application with invalid frequency."""
    lender = Lender(
        id=uuid4(),
        legal_name="Test",
        lender_type=LenderType.INDIVIDUAL,
        document_type="Cedula",
        document_number="1234567",
        email="test@test.com",
        phone="18091234567",
        status=LenderStatus.ACTIVE,
    )
    db_session.add(lender)

    customer = Customer(
        id=uuid4(),
        lender_id=lender.id,
        first_name="John",
        last_name="Doe",
        email="john@test.com",
        phone="18091234567",
        document_type="Cedula",
        document_number="123",
        status="active",
        credit_limit=Decimal("5000.00"),
    )
    db_session.add(customer)
    await db_session.commit()

    service = LoanApplicationService(db_session)
    with pytest.raises(ValidationException):
        await service.create_application(
            customer_id=str(customer.id),
            lender_id=str(lender.id),
            requested_amount=Decimal("1000.00"),
            requested_interest_rate=Decimal("5.0"),
            requested_installments_count=12,
            requested_frequency="invalid_frequency",  # Invalid!
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
