"""Database seed script - populate initial test data."""

import asyncio
from datetime import datetime, timezone, timedelta, date
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
    CustomerStatus,
    LoanApplicationStatus,
    LoanStatus,
    InstallmentStatus,
)
from app.core.security import hash_password
from app.core.utils import generate_installment_schedule
from app.db.base import Base
from app.models.lender import Lender
from app.models.user import User
from app.models.customer import Customer
from app.models.loan import Loan, Installment, Disbursement
from app.models.loan_application import LoanApplication
from app.models.subscription import Subscription
from app.models.notification import Notification


async def seed_database():
    """Seed the database with realistic test data."""
    engine = create_async_engine(settings.database_url, echo=False)

    AsyncSessionFactory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionFactory() as session:
        try:
            print("Seeding database...")

            lender_id = uuid4()
            lender = Lender(
                id=lender_id,
                legal_name="MicroFinanciera Dominica SRL",
                commercial_name="MicroCred",
                lender_type=LenderType.FINANCIAL,
                document_type="cedula",
                document_number="130987654",
                email="admin@microcred.com",
                phone="+1-809-555-0100",
                status=LenderStatus.ACTIVE,
                subscription_plan="basic",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(lender)
            await session.flush()

            owner_user = User(
                id=uuid4(),
                lender_id=lender_id,
                email="admin@microcred.com",
                password_hash=hash_password("Admin@12345"),
                first_name="Carlos",
                last_name="Rodriguez",
                role=UserRole.OWNER,
                account_type=AccountType.INTERNAL,
                status=UserStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(owner_user)

            manager_user = User(
                id=uuid4(),
                lender_id=lender_id,
                email="gerente@microcred.com",
                password_hash=hash_password("Gerente@12345"),
                first_name="Maria",
                last_name="Santos",
                role=UserRole.MANAGER,
                account_type=AccountType.INTERNAL,
                status=UserStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(manager_user)

            agent_user = User(
                id=uuid4(),
                lender_id=lender_id,
                email="agente@microcred.com",
                password_hash=hash_password("Agente@12345"),
                first_name="Juan",
                last_name="Perez",
                role=UserRole.AGENT,
                account_type=AccountType.INTERNAL,
                status=UserStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(agent_user)
            await session.flush()

            customers = []
            customers_data = [
                {
                    "first": "Ana",
                    "last": "Gomez",
                    "doc": "40234567891",
                    "email": "ana.gomez@email.com",
                    "phone": "+1-809-555-0201",
                },
                {
                    "first": "Luis",
                    "last": "Fernandez",
                    "doc": "40223456782",
                    "email": "luis.fernandez@email.com",
                    "phone": "+1-809-555-0202",
                },
                {
                    "first": "Carmen",
                    "last": "Diaz",
                    "doc": "40212345673",
                    "email": "carmen.diaz@email.com",
                    "phone": "+1-809-555-0203",
                },
                {
                    "first": "Pedro",
                    "last": "Martinez",
                    "doc": "40298765434",
                    "email": "pedro.martinez@email.com",
                    "phone": "+1-809-555-0204",
                },
                {
                    "first": "Rosa",
                    "last": "Hernandez",
                    "doc": "40287654345",
                    "email": "rosa.hernandez@email.com",
                    "phone": "+1-809-555-0205",
                },
            ]

            for cdata in customers_data:
                customer_user_id = uuid4()
                customer_user = User(
                    id=customer_user_id,
                    lender_id=lender_id,
                    email=cdata["email"],
                    password_hash=hash_password("Cliente@12345"),
                    first_name=cdata["first"],
                    last_name=cdata["last"],
                    role=UserRole.CUSTOMER,
                    account_type=AccountType.CUSTOMER,
                    status=UserStatus.ACTIVE,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(customer_user)
                await session.flush()

                customer = Customer(
                    id=uuid4(),
                    lender_id=lender_id,
                    user_id=customer_user_id,
                    first_name=cdata["first"],
                    last_name=cdata["last"],
                    document_type="cedula",
                    document_number=cdata["doc"],
                    phone=cdata["phone"],
                    email=cdata["email"],
                    status=CustomerStatus.ACTIVE,
                    credit_limit=Decimal("100000"),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(customer)
                await session.flush()
                customers.append(customer)

            loan_configs = [
                {
                    "customer_idx": 0,
                    "principal": Decimal("25000"),
                    "rate": Decimal("12"),
                    "installments": 6,
                },
                {
                    "customer_idx": 1,
                    "principal": Decimal("15000"),
                    "rate": Decimal("10"),
                    "installments": 4,
                },
                {
                    "customer_idx": 2,
                    "principal": Decimal("50000"),
                    "rate": Decimal("15"),
                    "installments": 12,
                },
                {
                    "customer_idx": 3,
                    "principal": Decimal("8000"),
                    "rate": Decimal("8"),
                    "installments": 3,
                },
            ]

            for idx, config in enumerate(loan_configs):
                customer = customers[config["customer_idx"]]
                principal = config["principal"]
                rate = config["rate"]
                num_installments = config["installments"]

                app = LoanApplication(
                    id=uuid4(),
                    lender_id=lender_id,
                    customer_id=customer.id,
                    requested_amount=principal,
                    requested_interest_rate=rate,
                    requested_installments_count=num_installments,
                    requested_frequency="monthly",
                    status=LoanApplicationStatus.APPROVED,
                    reviewed_at=datetime.now(timezone.utc)
                    - timedelta(days=20 - idx * 5),
                    review_notes="Aprobado",
                    created_at=datetime.now(timezone.utc)
                    - timedelta(days=30 - idx * 5),
                    updated_at=datetime.now(timezone.utc)
                    - timedelta(days=25 - idx * 5),
                )
                session.add(app)
                await session.flush()

                first_due = datetime.combine(
                    date.today() + timedelta(days=30), datetime.min.time()
                )
                schedule = generate_installment_schedule(
                    principal=float(principal),
                    annual_interest_rate=float(rate),
                    num_installments=num_installments,
                    frequency="monthly",
                    start_date=first_due,
                )

                total_interest = sum(
                    Decimal(str(s["interest_component"])) for s in schedule
                )
                total_amount = principal + total_interest

                loan = Loan(
                    id=uuid4(),
                    lender_id=lender_id,
                    customer_id=customer.id,
                    loan_application_id=app.id,
                    loan_number=f"LN-MICR-{datetime.now().strftime('%Y%m%d')}-{str(uuid4())[:8].upper()}",
                    principal_amount=principal,
                    interest_rate=rate,
                    interest_type="fixed",
                    total_interest_amount=total_interest,
                    total_amount=total_amount,
                    installments_count=num_installments,
                    frequency="monthly",
                    first_due_date=first_due.date(),
                    status=LoanStatus.ACTIVE,
                    approved_by=manager_user.id,
                    approved_at=datetime.now(timezone.utc)
                    - timedelta(days=20 - idx * 5),
                    disbursement_date=date.today() - timedelta(days=15 - idx * 5),
                    created_at=datetime.now(timezone.utc)
                    - timedelta(days=20 - idx * 5),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(loan)
                await session.flush()

                disbursement = Disbursement(
                    id=uuid4(),
                    loan_id=loan.id,
                    amount=principal,
                    method="bank_transfer",
                    status="completed",
                    created_by=manager_user.id,
                    disbursed_at=datetime.now(timezone.utc)
                    - timedelta(days=15 - idx * 5),
                    created_at=datetime.now(timezone.utc)
                    - timedelta(days=15 - idx * 5),
                )
                session.add(disbursement)

                for inst_data in schedule:
                    inst = Installment(
                        id=uuid4(),
                        loan_id=loan.id,
                        installment_number=inst_data["installment_number"],
                        due_date=inst_data["due_date"].date(),
                        principal_component=inst_data["principal_component"],
                        interest_component=inst_data["interest_component"],
                        amount_due=inst_data["amount"],
                        amount_paid=Decimal("0"),
                        late_fee_amount=Decimal("0"),
                        status=InstallmentStatus.PENDING,
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(inst)

            subscription = Subscription(
                id=uuid4(),
                lender_id=lender_id,
                plan_id="basic_monthly",
                status="trial",
                current_period_start=datetime.now(timezone.utc),
                current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
                cancel_at_period_end=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(subscription)

            notif1 = Notification(
                id=uuid4(),
                user_id=owner_user.id,
                title="Bienvenido a Kashap",
                message="Tu cuenta ha sido creada exitosamente.",
                notification_type="welcome",
                is_read=False,
                created_at=datetime.now(timezone.utc),
            )
            session.add(notif1)

            await session.commit()

            print("\n[OK] Database seeded successfully!")
            print(f"   Lender: MicroCred (ID: {lender_id})")
            print("\n   USERS:")
            print("   - admin@microcred.com / Admin@12345 (OWNER)")
            print("   - gerente@microcred.com / Gerente@12345 (MANAGER)")
            print("   - agente@microcred.com / Agente@12345 (AGENT)")
            print("   - ana.gomez@email.com / Cliente@12345 (CUSTOMER)")
            print("   - luis.fernandez@email.com / Cliente@12345 (CUSTOMER)")
            print("\n   4 loans created with installments")
            print("   5 customers created")

        except Exception as e:
            await session.rollback()
            print(f"[ERROR] Seed failed: {e}")
            import traceback

            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())
