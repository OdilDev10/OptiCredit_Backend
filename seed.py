"""Database seed script - populate initial data."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.core.enums import (
    LenderType,
    LenderStatus,
    UserRole,
    UserStatus,
    AccountType,
)
from app.core.security import hash_password
# Import all models to ensure relationships are registered
from app.db.base import Base
from app.models.lender import Lender
from app.models.user import User
from app.models.customer import Customer
from app.models.loan import Loan, Installment, Disbursement
from app.models.loan_application import LoanApplication
from app.models.payment import Payment, Voucher, OcrResult, PaymentMatch
from app.models.auth import EmailVerification, PasswordReset, OTP


async def seed_database():
    """Seed the database with initial data."""
    # Create engine
    engine = create_async_engine(settings.database_url, echo=True)

    # Create session factory
    AsyncSessionFactory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionFactory() as session:
        try:
            # Create a test lender
            lender_id = str(uuid4())
            lender = Lender(
                id=lender_id,
                legal_name="Test Lender LLC",
                commercial_name="Test Lender",
                lender_type=LenderType.INDIVIDUAL,
                document_type="cedula",
                document_number="123456789",
                email="lender@test.com",
                phone="+1-809-555-0001",
                status=LenderStatus.ACTIVE,
                subscription_plan="free",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(lender)
            await session.flush()

            # Create a test user with login credentials
            user = User(
                id=str(uuid4()),
                lender_id=lender_id,
                email="odil.martinez@odineck.com",
                password_hash=hash_password("Test@1234"),
                first_name="Odil",
                last_name="Martinez",
                role=UserRole.AGENT,
                account_type=AccountType.LENDER,
                status=UserStatus.ACTIVE,
                is_email_verified=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(user)

            await session.commit()
            print("[OK] Database seeded successfully!")
            print(f"   Lender ID: {lender_id}")
            print(f"   User: odil.martinez@odineck.com")
            print(f"   Password: Test@1234")

        except Exception as e:
            await session.rollback()
            print(f"[ERROR] Seed failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())
