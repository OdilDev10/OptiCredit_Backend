"""Loan Products API - publicly available loan products from lenders."""

from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, conint
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.lender import Lender
from app.models.lender import LenderBankAccount
from app.models.loan_product import LoanProduct
from app.models.user import User
from app.models.customer import Customer
from app.models.customer_lender_link import CustomerLenderLink
from app.core.enums import LenderStatus
from app.core.enums import LinkStatus
from app.dependencies import get_current_user
from app.repositories.customer_repo import CustomerRepository
from app.services.loan_application_service import LoanApplicationService
from app.core.exceptions import NotFoundException, ForbiddenException


router = APIRouter(prefix="/loan-products", tags=["loan-products"])


class LoanProductLender(BaseModel):
    """Lender info for loan product."""

    id: str
    name: str
    type: str
    logo_url: str | None = None


class LoanProductItem(BaseModel):
    """Loan product item."""

    id: str
    lender: LoanProductLender
    name: str
    description: str
    tier: str
    min_amount: float
    max_amount: float
    min_installments: int
    max_installments: int
    annual_interest_rate: float
    example_amount: float
    example_monthly_payment: float
    is_featured: bool


class LoanProductFilters(BaseModel):
    """Available filters for loan products."""

    institutions: list[dict]
    amount_ranges: list[dict]
    installment_ranges: list[dict]


class PaginatedLoanProductsResponse(BaseModel):
    """Paginated loan products response."""

    items: list[LoanProductItem]
    total: int
    skip: int
    limit: int


# Default interest rates and terms by lender type
DEFAULT_PRODUCTS = {
    "bank": {
        "min_amount": 10000,
        "max_amount": 500000,
        "min_installments": 6,
        "max_installments": 60,
        "annual_interest_rate": 0.18,
        "description": "Préstamo personal con tasas competitivas",
    },
    "credit_union": {
        "min_amount": 5000,
        "max_amount": 200000,
        "min_installments": 3,
        "max_installments": 48,
        "annual_interest_rate": 0.15,
        "description": "Crédito cooperativo con beneficios",
    },
    "individual": {
        "min_amount": 1000,
        "max_amount": 50000,
        "min_installments": 1,
        "max_installments": 24,
        "annual_interest_rate": 0.24,
        "description": "Crédito rápido y accesible",
    },
    "company": {
        "min_amount": 20000,
        "max_amount": 1000000,
        "min_installments": 12,
        "max_installments": 84,
        "annual_interest_rate": 0.12,
        "description": "Financiamiento empresarial integral",
    },
}


def _build_tiered_products(base: dict) -> list[dict]:
    """Build multiple commercial offers from a base product profile."""
    min_amount = float(base["min_amount"])
    max_amount = float(base["max_amount"])
    min_installments = int(base["min_installments"])
    max_installments = int(base["max_installments"])
    base_rate = float(base["annual_interest_rate"])

    mid_amount = round((min_amount + max_amount) / 2, 2)
    mid_installments = max(min_installments, min(max_installments, int((min_installments + max_installments) / 2)))

    return [
        {
            "tier": "Starter",
            "description_suffix": "Ideal para montos iniciales",
            "min_amount": min_amount,
            "max_amount": max(min_amount, round(mid_amount * 0.75, 2)),
            "min_installments": min_installments,
            "max_installments": max(min_installments, int(mid_installments * 0.8)),
            "annual_interest_rate": max(0.03, round(base_rate + 0.03, 4)),
        },
        {
            "tier": "Estándar",
            "description_suffix": "Balance entre cuota y plazo",
            "min_amount": max(min_amount, round(mid_amount * 0.5, 2)),
            "max_amount": max_amount,
            "min_installments": min_installments,
            "max_installments": max_installments,
            "annual_interest_rate": round(base_rate, 4),
        },
        {
            "tier": "Preferencial",
            "description_suffix": "Mejor tasa para montos altos",
            "min_amount": max(min_amount, round(mid_amount, 2)),
            "max_amount": max_amount,
            "min_installments": max(min_installments, int(mid_installments)),
            "max_installments": max_installments,
            "annual_interest_rate": max(0.02, round(base_rate - 0.02, 4)),
        },
    ]


def _calculate_monthly_payment(
    principal: float, annual_rate: float, months: int
) -> float:
    """Calculate monthly payment for a loan."""
    if months <= 0:
        return 0
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return principal / months
    payment = (
        principal
        * (monthly_rate * (1 + monthly_rate) ** months)
        / ((1 + monthly_rate) ** months - 1)
    )
    return round(payment, 2)


@router.get("", response_model=PaginatedLoanProductsResponse)
async def list_loan_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    lender_id: UUID | None = Query(default=None),
    min_amount: float | None = Query(default=None),
    max_amount: float | None = Query(default=None),
    min_installments: int | None = Query(default=None),
    max_installments: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> PaginatedLoanProductsResponse:
    """List publicly available loan products from active lenders."""

    # Query active lenders
    query = select(Lender).where(Lender.status == LenderStatus.ACTIVE)

    if lender_id:
        query = query.where(Lender.id == lender_id)

    result = await session.execute(query)
    lenders = result.scalars().all()

    items = []
    for lender in lenders:
        name = lender.commercial_name or lender.legal_name
        lender_type = (
            lender.lender_type.value
            if hasattr(lender.lender_type, "value")
            else str(lender.lender_type)
        )

        db_products_result = await session.execute(
            select(LoanProduct)
            .where(
                LoanProduct.lender_id == lender.id,
                LoanProduct.is_active.is_(True),
            )
            .order_by(LoanProduct.sort_order.asc(), LoanProduct.created_at.asc())
        )
        db_products = db_products_result.scalars().all()

        if db_products:
            for product in db_products:
                # Filter by search
                if search:
                    search_lower = search.lower()
                    if (
                        search_lower not in name.lower()
                        and search_lower not in product.name.lower()
                        and search_lower not in product.description.lower()
                        and search_lower not in product.tier.lower()
                    ):
                        continue

                # Apply filters
                if min_amount and float(product.max_amount) < min_amount:
                    continue
                if max_amount and float(product.min_amount) > max_amount:
                    continue
                if min_installments and product.max_installments < min_installments:
                    continue
                if max_installments and product.min_installments > max_installments:
                    continue

                example_amount = float(product.example_amount)
                example_payment = float(product.example_monthly_payment)
                if example_amount <= 0:
                    example_amount = min(float(product.max_amount), 50000)
                if example_payment <= 0:
                    example_months = min(product.max_installments, 24)
                    example_payment = _calculate_monthly_payment(
                        example_amount,
                        float(product.annual_interest_rate),
                        example_months,
                    )

                items.append(
                    LoanProductItem(
                        id=str(product.id),
                        lender=LoanProductLender(
                            id=str(lender.id),
                            name=name,
                            type=lender_type,
                            logo_url=None,
                        ),
                        name=product.name,
                        description=product.description,
                        tier=product.tier,
                        min_amount=float(product.min_amount),
                        max_amount=float(product.max_amount),
                        min_installments=product.min_installments,
                        max_installments=product.max_installments,
                        annual_interest_rate=float(product.annual_interest_rate),
                        example_amount=example_amount,
                        example_monthly_payment=example_payment,
                        is_featured=bool(product.is_featured),
                    )
                )
            continue

        # Fallback to default generated catalog only when lender has no configured products.
        product_config = DEFAULT_PRODUCTS.get(
            lender_type, DEFAULT_PRODUCTS["individual"]
        )
        tiered_products = _build_tiered_products(product_config)
        for tier_idx, tier_cfg in enumerate(tiered_products):
            product_name = f"{name} {tier_cfg['tier']}"
            product_description = (
                f"{product_config['description']}. {tier_cfg['description_suffix']}."
            )

            if search:
                search_lower = search.lower()
                if (
                    search_lower not in name.lower()
                    and search_lower not in product_description.lower()
                    and search_lower not in tier_cfg["tier"].lower()
                ):
                    continue

            if min_amount and tier_cfg["max_amount"] < min_amount:
                continue
            if max_amount and tier_cfg["min_amount"] > max_amount:
                continue
            if min_installments and tier_cfg["max_installments"] < min_installments:
                continue
            if max_installments and tier_cfg["min_installments"] > max_installments:
                continue

            example_amount = min(tier_cfg["max_amount"], 50000)
            example_months = min(tier_cfg["max_installments"], 24)
            example_payment = _calculate_monthly_payment(
                example_amount, tier_cfg["annual_interest_rate"], example_months
            )

            items.append(
                LoanProductItem(
                    id=f"{lender.id}-{tier_idx + 1}",
                    lender=LoanProductLender(
                        id=str(lender.id),
                        name=name,
                        type=lender_type,
                        logo_url=None,
                    ),
                    name=product_name,
                    description=product_description,
                    tier=tier_cfg["tier"],
                    min_amount=tier_cfg["min_amount"],
                    max_amount=tier_cfg["max_amount"],
                    min_installments=tier_cfg["min_installments"],
                    max_installments=tier_cfg["max_installments"],
                    annual_interest_rate=tier_cfg["annual_interest_rate"],
                    example_amount=example_amount,
                    example_monthly_payment=example_payment,
                    is_featured=lender.subscription_plan in ["professional", "enterprise"] and tier_idx == 2,
                )
            )

    total = len(items)
    return PaginatedLoanProductsResponse(
        items=items[skip : skip + limit],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/filters", response_model=LoanProductFilters)
async def get_loan_product_filters(
    session: AsyncSession = Depends(get_db),
) -> LoanProductFilters:
    """Get available filters for loan products."""
    return LoanProductFilters(
        institutions=[],
        amount_ranges=[
            {"min": 1000, "max": 10000},
            {"min": 10000, "max": 50000},
            {"min": 50000, "max": 100000},
            {"min": 100000, "max": 500000},
            {"min": 500000, "max": 1000000},
        ],
        installment_ranges=[
            {"min": 1, "max": 6},
            {"min": 6, "max": 12},
            {"min": 12, "max": 24},
            {"min": 24, "max": 48},
            {"min": 48, "max": 84},
        ],
    )


class CustomLoanRequest(BaseModel):
    """Request a custom loan from a specific lender."""

    lender_id: str
    requested_amount: float = Field(..., gt=0)
    requested_installments_count: conint(strict=True, ge=1, le=84)  # type: ignore[valid-type]
    purpose: str | None = None


class CustomLoanRequestResponse(BaseModel):
    """Response for custom loan request."""

    success: bool
    message: str
    application_id: str | None = None


@router.post("/request", response_model=CustomLoanRequestResponse)
async def request_custom_loan(
    request: CustomLoanRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CustomLoanRequestResponse:
    """Create a real loan application from an authenticated customer."""
    role_value = getattr(current_user.role, "value", current_user.role)
    if role_value != "customer":
        raise ForbiddenException("Customer account required")

    customer_repo = CustomerRepository(session)
    customer = await customer_repo.get_by_user_id(current_user.id)
    if customer is None:
        customer = await customer_repo.get_by_email_and_lender(current_user.email, current_user.lender_id)
    if customer is None:
        raise NotFoundException("No customer profile found for this user")

    # Find the lender
    lender_result = await session.execute(
        select(Lender).where(Lender.id == UUID(request.lender_id))
    )
    lender = lender_result.scalar_one_or_none()

    if not lender or lender.status != LenderStatus.ACTIVE:
        raise NotFoundException("Lender not found or not active")

    # Require active association with lender
    link_result = await session.execute(
        select(CustomerLenderLink).where(
            CustomerLenderLink.customer_id == customer.id,
            CustomerLenderLink.lender_id == lender.id,
            CustomerLenderLink.status == LinkStatus.LINKED,
        )
    )
    if link_result.scalar_one_or_none() is None:
        raise ForbiddenException("No active association with this lender")

    db_products_result = await session.execute(
        select(LoanProduct)
        .where(
            LoanProduct.lender_id == lender.id,
            LoanProduct.is_active.is_(True),
        )
        .order_by(LoanProduct.sort_order.asc(), LoanProduct.created_at.asc())
    )
    db_products = db_products_result.scalars().all()

    if db_products:
        matching_products = [
            p
            for p in db_products
            if float(p.min_amount) <= request.requested_amount <= float(p.max_amount)
            and p.min_installments
            <= request.requested_installments_count
            <= p.max_installments
        ]
        selected_rate = (
            float(matching_products[0].annual_interest_rate)
            if matching_products
            else float(db_products[0].annual_interest_rate)
        )
    else:
        lender_type = (
            lender.lender_type.value
            if hasattr(lender.lender_type, "value")
            else str(lender.lender_type)
        )
        base_product = DEFAULT_PRODUCTS.get(lender_type, DEFAULT_PRODUCTS["individual"])
        tiered_products = _build_tiered_products(base_product)
        selected_rate = tiered_products[1]["annual_interest_rate"]
        for tier_cfg in tiered_products:
            if (
                tier_cfg["min_amount"] <= request.requested_amount <= tier_cfg["max_amount"]
                and tier_cfg["min_installments"] <= request.requested_installments_count <= tier_cfg["max_installments"]
            ):
                selected_rate = tier_cfg["annual_interest_rate"]
                break

    service = LoanApplicationService(session)
    created = await service.create_application(
        customer_id=str(customer.id),
        lender_id=str(lender.id),
        requested_amount=Decimal(str(request.requested_amount)),
        requested_interest_rate=Decimal(str(round(selected_rate * 100, 2))),
        requested_installments_count=request.requested_installments_count,
        requested_frequency="monthly",
        purpose=request.purpose,
    )

    return CustomLoanRequestResponse(
        success=True,
        message=f"Solicitud enviada a {lender.commercial_name or lender.legal_name}. Te contactaremos pronto.",
        application_id=created.get("application_id"),
    )
