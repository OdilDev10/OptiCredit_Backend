"""Idempotent startup seed for rich development demo data."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select

# Ensure all ORM models are registered before querying.
from app.db import base as _base  # noqa: F401
from app.config import settings
from app.db.session import AsyncSessionFactory
from app.core.enums import (
    AccountType,
    CustomerStatus,
    LenderStatus,
    LenderType,
    LinkStatus,
    UserRole,
    UserStatus,
)
from app.core.security import hash_password
from app.core.utils import (
    generate_installment_schedule,
    generate_loan_number,
    generate_payment_number,
)
from app.models.client_bank_account import ClientBankAccount
from app.models.customer import Customer
from app.models.customer_lender_link import CustomerLenderLink
from app.models.lender import Lender, LenderBankAccount
from app.models.loan import (
    Disbursement,
    DisbursementStatus,
    Installment,
    InstallmentStatus,
    Loan,
    LoanStatus,
)
from app.models.loan_application import LoanApplication, LoanApplicationStatus
from app.models.payment import (
    OcrResult,
    OcrStatus,
    Payment,
    PaymentMethod,
    PaymentSource,
    PaymentStatus,
    Voucher,
    VoucherStatus,
)
from app.models.user import User

logger = logging.getLogger("app.seed")
logger.setLevel(logging.INFO)

TEST_USER_PASSWORD = "Test@1234"

SEED_LENDERS: dict[str, dict[str, Any]] = {
    "opticredit": {
        "legal_name": "OptiCredit Demo SRL",
        "commercial_name": "OptiCredit Demo",
        "lender_type": LenderType.FINANCIAL,
        "document_type": "RNC",
        "document_number": "40200000001",
        "email": "lender@opticredit.app",
        "phone": "8090000000",
        "address_line": "Av. Winston Churchill 95, Santo Domingo",
        "status": LenderStatus.ACTIVE,
        "subscription_plan": "professional",
    },
    "microcred": {
        "legal_name": "MicroFinanciera Dominica SRL",
        "commercial_name": "MicroCred",
        "lender_type": LenderType.FINANCIAL,
        "document_type": "RNC",
        "document_number": "40200000002",
        "email": "admin@microcred.com",
        "phone": "8095550100",
        "address_line": "Calle Duarte 21, Santiago",
        "status": LenderStatus.ACTIVE,
        "subscription_plan": "basic",
    },
    "crediplus": {
        "legal_name": "CrédiPlus Dominicana SRL",
        "commercial_name": "CrédiPlus",
        "lender_type": LenderType.FINANCIAL,
        "document_type": "RNC",
        "document_number": "40200000007",
        "email": "contacto@crediplus.do",
        "phone": "8095550777",
        "address_line": "Av. Abraham Lincoln 155, Santo Domingo",
        "status": LenderStatus.ACTIVE,
        "subscription_plan": "basic",
    },
    "coopnacional": {
        "legal_name": "Cooperativa Nacional de Ahorros y Préstamos",
        "commercial_name": "CoopNacional",
        "lender_type": LenderType.FINANCIAL,
        "document_type": "RNC",
        "document_number": "50123456789",
        "email": "contacto@coopnacional.com",
        "phone": "8095550300",
        "address_line": "Av. Máximo Gómez 45, Santo Domingo",
        "status": LenderStatus.PENDING,
        "subscription_plan": "professional",
        "rejection_reason": None,
    },
    "prestcaribe": {
        "legal_name": "Préstamos Rápidos del Caribe SRL",
        "commercial_name": "PrestCaribe",
        "lender_type": LenderType.INDIVIDUAL,
        "document_type": "Cédula",
        "document_number": "13123456789",
        "email": "admin@prestcaribe.com",
        "phone": "8095550400",
        "address_line": "Calle El Conde 78, Santo Domingo",
        "status": LenderStatus.PENDING,
        "subscription_plan": "basic",
        "rejection_reason": None,
    },
    "finexpress": {
        "legal_name": "Financiera Express SRL",
        "commercial_name": "FinExpress",
        "lender_type": LenderType.FINANCIAL,
        "document_type": "RNC",
        "document_number": "50198765432",
        "email": "info@finexpress.com",
        "phone": "8095550500",
        "address_line": "Av. 27 de Febrero 123, Santo Domingo",
        "status": LenderStatus.REJECTED,
        "subscription_plan": "enterprise",
        "rejection_reason": "Documentación incompleta: falta certificado de registro mercantil y referencias bancarias.",
    },
}

SEED_USERS: list[dict[str, Any]] = [
    {
        "email": "odil.martinez@opticredit.app",
        "first_name": "Odil",
        "last_name": "Martinez",
        "phone": "8091111111",
        "account_type": AccountType.INTERNAL,
        "role": UserRole.PLATFORM_ADMIN,
        "status": UserStatus.ACTIVE,
        "lender_key": None,
    },
    {
        "email": "lender@opticredit.app",
        "first_name": "Lender",
        "last_name": "Demo",
        "phone": "8090000000",
        "account_type": AccountType.LENDER,
        "role": UserRole.OWNER,
        "status": UserStatus.ACTIVE,
        "lender_key": "opticredit",
    },
    {
        "email": "manager@opticredit.app",
        "first_name": "Paola",
        "last_name": "Mejia",
        "phone": "8090000001",
        "account_type": AccountType.INTERNAL,
        "role": UserRole.MANAGER,
        "status": UserStatus.ACTIVE,
        "lender_key": "opticredit",
    },
    {
        "email": "agent@opticredit.app",
        "first_name": "Laura",
        "last_name": "Nunez",
        "phone": "8090000002",
        "account_type": AccountType.INTERNAL,
        "role": UserRole.AGENT,
        "status": UserStatus.ACTIVE,
        "lender_key": "opticredit",
    },
    {
        "email": "admin@microcred.com",
        "first_name": "Carlos",
        "last_name": "Rodriguez",
        "phone": "8095550100",
        "account_type": AccountType.LENDER,
        "role": UserRole.OWNER,
        "status": UserStatus.ACTIVE,
        "lender_key": "microcred",
    },
    {
        "email": "cliente@opticredit.app",
        "first_name": "Cliente",
        "last_name": "Demo",
        "phone": "8092222222",
        "account_type": AccountType.CUSTOMER,
        "role": UserRole.CUSTOMER,
        "status": UserStatus.ACTIVE,
        "lender_key": None,
    },
    {
        "email": "cliente.solicitud@opticredit.app",
        "first_name": "Cliente",
        "last_name": "Solicitud",
        "phone": "8093333333",
        "account_type": AccountType.CUSTOMER,
        "role": UserRole.CUSTOMER,
        "status": UserStatus.ACTIVE,
        "lender_key": None,
    },
]

CUSTOMER_ASSOCIATIONS_BY_EMAIL: dict[str, dict[str, list[str]]] = {
    "cliente@opticredit.app": {
        "linked": ["opticredit"],
        "pending": ["microcred"],
    },
    "cliente.solicitud@opticredit.app": {
        "linked": [],
        "pending": ["opticredit"],
    },
}

LENDER_ACCOUNTS: dict[str, list[dict[str, Any]]] = {
    "opticredit": [
        {
            "bank_name": "Banco Popular Dominicano",
            "account_type": "checking",
            "account_number_masked": "8870011204",
            "account_holder_name": "OptiCredit Demo SRL",
            "currency": "DOP",
            "is_primary": True,
            "status": "active",
        },
        {
            "bank_name": "Banco BHD",
            "account_type": "savings",
            "account_number_masked": "1120094458",
            "account_holder_name": "OptiCredit Demo SRL",
            "currency": "DOP",
            "is_primary": False,
            "status": "active",
        },
    ],
    "microcred": [
        {
            "bank_name": "Banreservas",
            "account_type": "checking",
            "account_number_masked": "7785508831",
            "account_holder_name": "MicroFinanciera Dominica SRL",
            "currency": "DOP",
            "is_primary": True,
            "status": "active",
        }
    ],
}

CLIENT_ACCOUNTS = [
    {
        "bank_name": "Banco Popular Dominicano",
        "account_type": "savings",
        "account_number_masked": "*********9922",
        "account_holder_name": "Cliente Demo",
        "currency": "DOP",
        "is_primary": True,
        "status": "active",
        "balance": Decimal("2400.00"),
    },
    {
        "bank_name": "Banco BHD",
        "account_type": "checking",
        "account_number_masked": "*********7710",
        "account_holder_name": "Cliente Demo",
        "currency": "DOP",
        "is_primary": False,
        "status": "active",
        "balance": Decimal("0.00"),
    },
]

SEED_LOANS = [
    {
        "code": "OPTI-ACT-001",
        "lender_key": "opticredit",
        "principal": Decimal("250000.00"),
        "annual_rate": Decimal("22.00"),
        "installments_count": 12,
        "frequency": "monthly",
        "first_due_offset_days": -60,
        "disbursement_offset_days": 95,
        "status": LoanStatus.ACTIVE,
        "paid_installments": {1: Decimal("25458.33")},
        "partial_installments": {2: Decimal("12000.00")},
    },
    {
        "code": "OPTI-OVD-002",
        "lender_key": "opticredit",
        "principal": Decimal("90000.00"),
        "annual_rate": Decimal("30.00"),
        "installments_count": 6,
        "frequency": "monthly",
        "first_due_offset_days": -120,
        "disbursement_offset_days": 140,
        "status": LoanStatus.OVERDUE,
        "paid_installments": {1: Decimal("15750.00")},
        "partial_installments": {},
    },
    {
        "code": "MIC-ACT-003",
        "lender_key": "microcred",
        "principal": Decimal("60000.00"),
        "annual_rate": Decimal("18.00"),
        "installments_count": 8,
        "frequency": "monthly",
        "first_due_offset_days": -20,
        "disbursement_offset_days": 55,
        "status": LoanStatus.ACTIVE,
        "paid_installments": {},
        "partial_installments": {},
    },
]


async def _upsert_lender(session, payload: dict[str, Any]) -> Lender:
    result = await session.execute(
        select(Lender).where(Lender.email == payload["email"])
    )
    lender = result.scalar_one_or_none()

    if lender is None:
        lender = Lender(**payload)
        session.add(lender)
        await session.flush()
        logger.info("Startup seed created lender: %s", payload["email"])
        return lender

    for key, value in payload.items():
        setattr(lender, key, value)
    logger.info("Startup seed updated lender: %s", payload["email"])
    return lender


async def _upsert_user(
    session, payload: dict[str, Any], lender_map: dict[str, Lender]
) -> User:
    result = await session.execute(select(User).where(User.email == payload["email"]))
    user = result.scalar_one_or_none()
    lender = lender_map.get(payload["lender_key"]) if payload["lender_key"] else None

    user_values = {
        "first_name": payload["first_name"],
        "last_name": payload["last_name"],
        "phone": payload["phone"],
        "email": payload["email"],
        "password_hash": hash_password(TEST_USER_PASSWORD),
        "account_type": payload["account_type"],
        "role": payload["role"],
        "status": payload["status"],
        "lender_id": lender.id if lender else None,
    }

    if user is None:
        user = User(**user_values)
        session.add(user)
        await session.flush()
        logger.info("Startup seed created user: %s", payload["email"])
        return user

    for key, value in user_values.items():
        setattr(user, key, value)
    logger.info("Startup seed updated user: %s", payload["email"])
    return user


async def _upsert_customer_profile(
    session,
    customer_user: User,
    default_lender: Lender,
    *,
    document_number: str,
) -> Customer:
    result = await session.execute(
        select(Customer).where(Customer.user_id == customer_user.id)
    )
    customer = result.scalar_one_or_none()

    values = {
        "lender_id": default_lender.id,
        "user_id": customer_user.id,
        "first_name": customer_user.first_name,
        "last_name": customer_user.last_name,
        "document_type": "Cédula",
        "document_number": document_number,
        "phone": customer_user.phone or "8092222222",
        "email": customer_user.email,
        "status": CustomerStatus.ACTIVE,
        "credit_limit": Decimal("350000.00"),
        "city": "Santo Domingo",
        "province": "Distrito Nacional",
        "country": "DO",
    }

    if customer is None:
        customer = Customer(**values)
        session.add(customer)
        await session.flush()
        logger.info("Startup seed created customer profile: %s", customer_user.email)
        return customer

    for key, value in values.items():
        setattr(customer, key, value)
    logger.info("Startup seed updated customer profile: %s", customer_user.email)
    return customer


async def _ensure_customer_links(
    session,
    customer: Customer,
    lender_map: dict[str, Lender],
    *,
    linked_lender_keys: list[str],
    pending_lender_keys: list[str],
) -> None:
    desired_status_by_lender: dict[str, LinkStatus] = {
        lender_key: LinkStatus.LINKED
        for lender_key in linked_lender_keys
    }
    desired_status_by_lender.update(
        {
            lender_key: LinkStatus.PENDING
            for lender_key in pending_lender_keys
        }
    )

    for lender_key, lender in lender_map.items():
        result = await session.execute(
            select(CustomerLenderLink).where(
                CustomerLenderLink.customer_id == customer.id,
                CustomerLenderLink.lender_id == lender.id,
            )
        )
        link = result.scalar_one_or_none()
        desired_status = desired_status_by_lender.get(lender_key)

        if desired_status is None:
            if link is not None and link.status != LinkStatus.UNLINKED:
                link.status = LinkStatus.UNLINKED
            continue

        if link is None:
            link = CustomerLenderLink(
                customer_id=customer.id,
                lender_id=lender.id,
                status=desired_status,
            )
            session.add(link)
        else:
            link.status = desired_status


async def _upsert_lender_accounts(
    session, lender: Lender, accounts: list[dict[str, Any]]
) -> None:
    for account_data in accounts:
        expected_last4 = account_data["account_number_masked"][-4:]
        by_bank_result = await session.execute(
            select(LenderBankAccount).where(
                and_(
                    LenderBankAccount.lender_id == lender.id,
                    LenderBankAccount.bank_name == account_data["bank_name"],
                    LenderBankAccount.status != "deleted",
                )
            )
        )
        existing_by_bank = by_bank_result.scalars().all()
        account = next(
            (
                acc
                for acc in existing_by_bank
                if acc.account_number_masked[-4:] == expected_last4
            ),
            None,
        )
        if account is None:
            account = next(
                (
                    acc
                    for acc in existing_by_bank
                    if acc.account_holder_name == account_data["account_holder_name"]
                    and acc.account_type == account_data["account_type"]
                ),
                None,
            )

        if account is None:
            account = LenderBankAccount(lender_id=lender.id, **account_data)
            session.add(account)
            continue

        result = await session.execute(
            select(LenderBankAccount).where(
                and_(
                    LenderBankAccount.lender_id == lender.id,
                    LenderBankAccount.bank_name == account_data["bank_name"],
                    LenderBankAccount.account_number_masked
                    == account_data["account_number_masked"],
                )
            )
        )
        exact_match = result.scalar_one_or_none()
        if exact_match is not None:
            account = exact_match

        for key, value in account_data.items():
            setattr(account, key, value)


async def _upsert_client_accounts(session, customer: Customer) -> None:
    for account_data in CLIENT_ACCOUNTS:
        result = await session.execute(
            select(ClientBankAccount).where(
                and_(
                    ClientBankAccount.customer_id == customer.id,
                    ClientBankAccount.bank_name == account_data["bank_name"],
                    ClientBankAccount.account_number_masked
                    == account_data["account_number_masked"],
                )
            )
        )
        account = result.scalar_one_or_none()

        if account is None:
            account = ClientBankAccount(customer_id=customer.id, **account_data)
            session.add(account)
            continue

        for key, value in account_data.items():
            setattr(account, key, value)


async def _normalize_lender_primary_account(
    session,
    lender_id,
    preferred_masked: str | None = None,
) -> None:
    result = await session.execute(
        select(LenderBankAccount)
        .where(
            LenderBankAccount.lender_id == lender_id,
            LenderBankAccount.status != "deleted",
        )
        .order_by(LenderBankAccount.created_at.asc())
    )
    accounts = result.scalars().all()
    if not accounts:
        return

    primary = None
    if preferred_masked:
        primary = next(
            (acc for acc in accounts if acc.account_number_masked == preferred_masked),
            None,
        )
    if primary is None:
        primary = next((acc for acc in accounts if acc.is_primary), None) or accounts[0]

    for acc in accounts:
        acc.is_primary = acc.id == primary.id


async def _normalize_client_primary_account(
    session,
    customer_id,
    preferred_masked: str | None = None,
) -> None:
    result = await session.execute(
        select(ClientBankAccount)
        .where(
            ClientBankAccount.customer_id == customer_id,
            ClientBankAccount.status != "deleted",
        )
        .order_by(ClientBankAccount.created_at.asc())
    )
    accounts = result.scalars().all()
    if not accounts:
        return

    primary = None
    if preferred_masked:
        primary = next(
            (acc for acc in accounts if acc.account_number_masked == preferred_masked),
            None,
        )
    if primary is None:
        primary = next((acc for acc in accounts if acc.is_primary), None) or accounts[0]

    for acc in accounts:
        acc.is_primary = acc.id == primary.id


def _calc_installment_status(
    due_date: date,
    amount_due: Decimal,
    amount_paid: Decimal,
) -> InstallmentStatus:
    if amount_paid >= amount_due:
        return InstallmentStatus.PAID
    if amount_paid > Decimal("0"):
        return InstallmentStatus.PARTIAL
    if due_date < date.today():
        return InstallmentStatus.OVERDUE
    return InstallmentStatus.PENDING


async def _upsert_seed_payment(
    session,
    *,
    marker: str,
    lender: Lender,
    customer: Customer,
    loan: Loan,
    installment: Installment,
    submitted_by_user_id,
    amount: Decimal,
    status: PaymentStatus,
    voucher_status: VoucherStatus | None,
    with_ocr: bool,
    counters: dict[str, int],
    year: int,
) -> None:
    result = await session.execute(
        select(Payment).where(Payment.review_notes == marker)
    )
    payment = result.scalar_one_or_none()

    reviewed_at = (
        datetime.now(timezone.utc)
        if status in {PaymentStatus.UNDER_REVIEW, PaymentStatus.APPROVED}
        else None
    )
    reviewed_by_user_id = submitted_by_user_id if reviewed_at else None

    if payment is None:
        counters["payment"] += 1
        payment_number = generate_payment_number(counters["payment"], year)
    else:
        payment_number = payment.payment_number

    payment_values = {
        "lender_id": lender.id,
        "customer_id": customer.id,
        "loan_id": loan.id,
        "installment_id": installment.id,
        "payment_number": payment_number,
        "amount": amount,
        "currency": "DOP",
        "method": PaymentMethod.BANK_TRANSFER,
        "source": PaymentSource.CUSTOMER_PORTAL,
        "status": status,
        "submitted_by_user_id": submitted_by_user_id,
        "reviewed_by_user_id": reviewed_by_user_id,
        "reviewed_at": reviewed_at,
        "review_notes": marker,
    }

    if payment is None:
        payment = Payment(**payment_values)
        session.add(payment)
        await session.flush()
    else:
        for key, value in payment_values.items():
            setattr(payment, key, value)

    if voucher_status is None:
        return

    def _seed_voucher_public_url(seed_hash: str) -> str:
        public_base = settings.r2_public_url.strip().rstrip("/")
        if public_base:
            return f"{public_base}/vouchers/seed/{seed_hash}.jpg"
        return f"https://placehold.co/1200x800.jpg?text={seed_hash}"

    image_hash = f"seed-{marker.lower().replace(':', '-')}"
    voucher_result = await session.execute(
        select(Voucher).where(Voucher.image_hash == image_hash)
    )
    voucher = voucher_result.scalar_one_or_none()
    voucher_values = {
        "payment_id": payment.id,
        "original_file_url": _seed_voucher_public_url(image_hash),
        "processed_file_url": None,
        "mime_type": "image/jpeg",
        "file_size_bytes": "153600",
        "image_hash": image_hash,
        "upload_source": "web",
        "status": voucher_status,
    }

    if voucher is None:
        voucher = Voucher(**voucher_values)
        session.add(voucher)
        await session.flush()
    else:
        for key, value in voucher_values.items():
            setattr(voucher, key, value)

    ocr_result = await session.execute(
        select(OcrResult).where(OcrResult.voucher_id == voucher.id)
    )
    existing_ocr = ocr_result.scalar_one_or_none()
    if not with_ocr:
        if existing_ocr is not None:
            await session.delete(existing_ocr)
        return

    ocr_values = {
        "voucher_id": voucher.id,
        "extracted_text": "TRANSFERENCIA BANCARIA",
        "detected_amount": amount,
        "detected_currency": "DOP",
        "detected_date": date.today().isoformat(),
        "detected_reference": marker[-8:],
        "detected_bank_name": "Banco Popular Dominicano",
        "confidence_score": 0.93,
        "appears_to_be_receipt": True,
        "validation_summary": "Seed OCR result for demo flow.",
        "status": OcrStatus.SUCCESS,
    }
    if existing_ocr is None:
        session.add(OcrResult(**ocr_values))
    else:
        for key, value in ocr_values.items():
            setattr(existing_ocr, key, value)


async def _upsert_seed_loans(
    session,
    *,
    customer: Customer,
    manager_user: User,
    lender_map: dict[str, Lender],
    counters: dict[str, int],
) -> None:
    year = datetime.now().year
    for scenario in SEED_LOANS:
        lender = lender_map[scenario["lender_key"]]
        purpose = f"SEED:{scenario['code']}"

        app_result = await session.execute(
            select(LoanApplication).where(
                LoanApplication.customer_id == customer.id,
                LoanApplication.lender_id == lender.id,
                LoanApplication.purpose == purpose,
            )
        )
        application = app_result.scalar_one_or_none()
        if application is None:
            application = LoanApplication(
                lender_id=lender.id,
                customer_id=customer.id,
                requested_amount=scenario["principal"],
                requested_interest_rate=scenario["annual_rate"],
                requested_installments_count=scenario["installments_count"],
                requested_frequency=scenario["frequency"],
                purpose=purpose,
                status=LoanApplicationStatus.APPROVED,
                reviewed_by=manager_user.id,
                reviewed_at=datetime.now(timezone.utc),
                review_notes="Seed auto approved",
            )
            session.add(application)
            await session.flush()
        else:
            application.requested_amount = scenario["principal"]
            application.requested_interest_rate = scenario["annual_rate"]
            application.requested_installments_count = scenario["installments_count"]
            application.requested_frequency = scenario["frequency"]
            application.status = LoanApplicationStatus.APPROVED
            application.reviewed_by = manager_user.id
            application.reviewed_at = datetime.now(timezone.utc)
            application.review_notes = "Seed auto approved"

        lender_prefix = (
            lender.commercial_name[:4].upper().replace(" ", "")
            if lender.commercial_name
            else "LOAN"
        )

        loan_result = await session.execute(
            select(Loan).where(
                Loan.lender_id == lender.id,
                Loan.customer_id == customer.id,
                Loan.loan_application_id == application.id,
            )
        )
        loan = loan_result.scalar_one_or_none()

        if loan is None:
            counters["loan"] += 1
            loan_number = generate_loan_number(counters["loan"], lender_prefix, year)
        else:
            loan_number = loan.loan_number

        first_due_date = date.today() + timedelta(
            days=scenario["first_due_offset_days"]
        )
        schedule = generate_installment_schedule(
            principal=scenario["principal"],
            annual_interest_rate=scenario["annual_rate"],
            num_installments=scenario["installments_count"],
            frequency=scenario["frequency"],
            start_date=datetime.combine(first_due_date, datetime.min.time()),
        )
        total_interest = sum(item["interest_component"] for item in schedule)
        total_amount = scenario["principal"] + total_interest

        loan_values = {
            "lender_id": lender.id,
            "customer_id": customer.id,
            "loan_application_id": application.id,
            "loan_number": loan_number,
            "principal_amount": scenario["principal"],
            "interest_rate": scenario["annual_rate"],
            "interest_type": "fixed",
            "total_interest_amount": total_interest,
            "total_amount": total_amount,
            "installments_count": scenario["installments_count"],
            "frequency": scenario["frequency"],
            "disbursement_date": date.today()
            - timedelta(days=scenario["disbursement_offset_days"]),
            "first_due_date": first_due_date,
            "status": scenario["status"],
            "approved_by": manager_user.id,
            "approved_at": datetime.now(timezone.utc) - timedelta(days=2),
            "internal_notes": "Seed demo loan",
        }

        if loan is None:
            loan = Loan(**loan_values)
            session.add(loan)
            await session.flush()
        else:
            for key, value in loan_values.items():
                setattr(loan, key, value)

        dis_result = await session.execute(
            select(Disbursement).where(Disbursement.loan_id == loan.id)
        )
        disbursement = dis_result.scalars().first()
        dis_values = {
            "loan_id": loan.id,
            "amount": scenario["principal"],
            "method": "bank_transfer",
            "bank_name": "Banco Popular Dominicano",
            "reference_number": f"SEED-DISB-{scenario['code']}",
            "receipt_url": None,
            "status": DisbursementStatus.COMPLETED,
            "created_by": manager_user.id,
            "disbursed_at": datetime.now(timezone.utc) - timedelta(days=1),
        }
        if disbursement is None:
            session.add(Disbursement(**dis_values))
        else:
            for key, value in dis_values.items():
                setattr(disbursement, key, value)

        installments_by_number: dict[int, Installment] = {}
        existing_result = await session.execute(
            select(Installment).where(Installment.loan_id == loan.id)
        )
        for row in existing_result.scalars().all():
            installments_by_number[row.installment_number] = row

        for item in schedule:
            number = item["installment_number"]
            installment = installments_by_number.get(number)
            amount_due = item["amount"]
            amount_paid = scenario["paid_installments"].get(number, Decimal("0.00"))
            if number in scenario["partial_installments"]:
                amount_paid = scenario["partial_installments"][number]
            status = _calc_installment_status(
                item["due_date"].date(), amount_due, amount_paid
            )

            inst_values = {
                "loan_id": loan.id,
                "installment_number": number,
                "due_date": item["due_date"].date(),
                "principal_component": item["principal_component"],
                "interest_component": item["interest_component"],
                "amount_due": amount_due,
                "amount_paid": amount_paid,
                "late_fee_amount": Decimal("0.00"),
                "status": status,
                "paid_at": datetime.now(timezone.utc) - timedelta(days=1)
                if status == InstallmentStatus.PAID
                else None,
            }

            if installment is None:
                session.add(Installment(**inst_values))
            else:
                for key, value in inst_values.items():
                    setattr(installment, key, value)

        await session.flush()

        ordered_installments_result = await session.execute(
            select(Installment)
            .where(Installment.loan_id == loan.id)
            .order_by(Installment.installment_number.asc())
        )
        ordered_installments = ordered_installments_result.scalars().all()
        if not ordered_installments:
            continue

        first_installment = ordered_installments[0]
        await _upsert_seed_payment(
            session,
            marker=f"SEED:{loan_number}:APPROVED",
            lender=lender,
            customer=customer,
            loan=loan,
            installment=first_installment,
            submitted_by_user_id=customer.user_id,
            amount=first_installment.amount_due,
            status=PaymentStatus.APPROVED,
            voucher_status=VoucherStatus.PROCESSED,
            with_ocr=True,
            counters=counters,
            year=year,
        )

        second_installment = (
            ordered_installments[1]
            if len(ordered_installments) > 1
            else first_installment
        )
        await _upsert_seed_payment(
            session,
            marker=f"SEED:{loan_number}:UNDER_REVIEW",
            lender=lender,
            customer=customer,
            loan=loan,
            installment=second_installment,
            submitted_by_user_id=customer.user_id,
            amount=second_installment.amount_due,
            status=PaymentStatus.UNDER_REVIEW,
            voucher_status=VoucherStatus.PROCESSED,
            with_ocr=True,
            counters=counters,
            year=year,
        )

        pending_installment = (
            ordered_installments[2]
            if len(ordered_installments) > 2
            else second_installment
        )
        await _upsert_seed_payment(
            session,
            marker=f"SEED:{loan_number}:SUBMITTED",
            lender=lender,
            customer=customer,
            loan=loan,
            installment=pending_installment,
            submitted_by_user_id=customer.user_id,
            amount=pending_installment.amount_due,
            status=PaymentStatus.SUBMITTED,
            voucher_status=VoucherStatus.UPLOADED,
            with_ocr=False,
            counters=counters,
            year=year,
        )


async def run_startup_seed() -> None:
    """Create/update required dev data without duplicating records."""
    async with AsyncSessionFactory() as session:
        lender_map: dict[str, Lender] = {}
        for lender_key, lender_data in SEED_LENDERS.items():
            lender_map[lender_key] = await _upsert_lender(session, lender_data)

        user_map: dict[str, User] = {}
        for user_data in SEED_USERS:
            user_map[user_data["email"]] = await _upsert_user(
                session, user_data, lender_map
            )

        customer_documents = {
            "cliente@opticredit.app": "40200000003",
            "cliente.solicitud@opticredit.app": "40200000004",
        }
        customer_map: dict[str, Customer] = {}
        for email, associations in CUSTOMER_ASSOCIATIONS_BY_EMAIL.items():
            customer_user = user_map[email]
            customer = await _upsert_customer_profile(
                session,
                customer_user=customer_user,
                default_lender=lender_map["opticredit"],
                document_number=customer_documents[email],
            )
            customer_map[email] = customer
            await _ensure_customer_links(
                session,
                customer,
                lender_map,
                linked_lender_keys=associations.get("linked", []),
                pending_lender_keys=associations.get("pending", []),
            )

        customer = customer_map["cliente@opticredit.app"]

        for lender_key, accounts in LENDER_ACCOUNTS.items():
            await _upsert_lender_accounts(session, lender_map[lender_key], accounts)
            preferred = next(
                (
                    acc["account_number_masked"]
                    for acc in accounts
                    if acc.get("is_primary")
                ),
                None,
            )
            await _normalize_lender_primary_account(
                session,
                lender_map[lender_key].id,
                preferred_masked=preferred,
            )

        await _upsert_client_accounts(session, customer)
        preferred_client = next(
            (
                acc["account_number_masked"]
                for acc in CLIENT_ACCOUNTS
                if acc.get("is_primary")
            ),
            None,
        )
        await _normalize_client_primary_account(
            session,
            customer.id,
            preferred_masked=preferred_client,
        )

        manager_user = user_map["manager@opticredit.app"]
        counters: dict[str, int] = {
            "loan": 0,
            "payment": 0,
            "application": 0,
            "customer": 0,
            "user": 0,
        }
        await _upsert_seed_loans(
            session,
            customer=customer,
            manager_user=manager_user,
            lender_map=lender_map,
            counters=counters,
        )

        await session.commit()
        logger.info("Startup seed completed with enriched demo data.")
