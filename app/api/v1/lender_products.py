"""Lender Loan Products API - CRUD for lenders to manage their loan products."""

from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.dependencies import get_lender_context, require_roles
from app.models.user import User
from app.models.lender import Lender
from app.services.loan_product_service import LoanProductService


router = APIRouter(prefix="/lender/products", tags=["lender-products"])


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
    min_amount = float(base["min_amount"])
    max_amount = float(base["max_amount"])
    min_installments = int(base["min_installments"])
    max_installments = int(base["max_installments"])
    base_rate = float(base["annual_interest_rate"])

    mid_amount = round((min_amount + max_amount) / 2, 2)
    mid_installments = max(
        min_installments,
        min(max_installments, int((min_installments + max_installments) / 2)),
    )

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


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    tier: str = Field(default="standard", max_length=20)
    min_amount: float = Field(..., gt=0)
    max_amount: float = Field(..., gt=0)
    min_installments: int = Field(..., ge=1)
    max_installments: int = Field(..., ge=1)
    annual_interest_rate: float = Field(..., ge=0, le=1)
    example_amount: float | None = None
    example_monthly_payment: float | None = None
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = 0


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tier: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    min_installments: int | None = None
    max_installments: int | None = None
    annual_interest_rate: float | None = None
    example_amount: float | None = None
    example_monthly_payment: float | None = None
    is_active: bool | None = None
    is_featured: bool | None = None
    sort_order: int | None = None


class ProductResponse(BaseModel):
    id: str
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
    is_active: bool
    is_featured: bool
    sort_order: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PaginatedProductsResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    skip: int
    limit: int


def _product_to_response(product) -> ProductResponse:
    return ProductResponse(
        id=str(product.id),
        name=product.name,
        description=product.description,
        tier=product.tier,
        min_amount=float(product.min_amount),
        max_amount=float(product.max_amount),
        min_installments=product.min_installments,
        max_installments=product.max_installments,
        annual_interest_rate=float(product.annual_interest_rate),
        example_amount=float(product.example_amount),
        example_monthly_payment=float(product.example_monthly_payment),
        is_active=product.is_active,
        is_featured=product.is_featured,
        sort_order=product.sort_order,
        created_at=product.created_at.isoformat() if product.created_at else "",
        updated_at=product.updated_at.isoformat() if product.updated_at else "",
    )


@router.get("", response_model=PaginatedProductsResponse)
async def list_lender_products(
    active_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> PaginatedProductsResponse:
    """List all loan products for the lender (DB products + defaults if empty)."""
    service = LoanProductService(session)
    db_products = await service.get_lender_products(
        UUID(lender_id),
        active_only=active_only,
    )

    items: list[ProductResponse] = [_product_to_response(p) for p in db_products]

    if not db_products:
        lender_result = await session.execute(
            select(Lender).where(Lender.id == UUID(lender_id))
        )
        lender = lender_result.scalar_one_or_none()

        if lender:
            lender_type = (
                lender.lender_type.value
                if hasattr(lender.lender_type, "value")
                else str(lender.lender_type)
            )
            product_config = DEFAULT_PRODUCTS.get(
                lender_type, DEFAULT_PRODUCTS["individual"]
            )
            tiered_products = _build_tiered_products(product_config)

            for idx, tier_cfg in enumerate(tiered_products):
                tier_name = (
                    f"{lender.commercial_name or lender.legal_name} {tier_cfg['tier']}"
                )
                example_amount = min(tier_cfg["max_amount"], 50000)
                example_months = min(tier_cfg["max_installments"], 24)
                example_payment = _calculate_monthly_payment(
                    example_amount, tier_cfg["annual_interest_rate"], example_months
                )

                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)

                items.append(
                    ProductResponse(
                        id=f"default-{lender_id}-{idx + 1}",
                        name=tier_name,
                        description=f"{product_config['description']}. {tier_cfg['description_suffix']}.",
                        tier=tier_cfg["tier"].lower(),
                        min_amount=tier_cfg["min_amount"],
                        max_amount=tier_cfg["max_amount"],
                        min_installments=tier_cfg["min_installments"],
                        max_installments=tier_cfg["max_installments"],
                        annual_interest_rate=tier_cfg["annual_interest_rate"],
                        example_amount=example_amount,
                        example_monthly_payment=example_payment,
                        is_active=True,
                        is_featured=lender.subscription_plan
                        in ["professional", "enterprise"]
                        and idx == 2,
                        sort_order=idx,
                        created_at=now.isoformat(),
                        updated_at=now.isoformat(),
                    )
                )

    total = len(items)
    return PaginatedProductsResponse(
        items=items[skip : skip + limit], total=total, skip=skip, limit=limit
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_lender_product(
    product_id: UUID,
    current_user: User = Depends(
        require_roles("platform_admin", "owner", "manager", "reviewer")
    ),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Get a specific loan product."""
    service = LoanProductService(session)
    product = await service.repo.get_or_404(product_id, error_code="PRODUCT_NOT_FOUND")
    if str(product.lender_id) != lender_id:
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException("Product does not belong to this lender")
    return _product_to_response(product)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_lender_product(
    data: ProductCreate,
    current_user: User = Depends(require_roles("platform_admin", "owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Create a new loan product."""
    service = LoanProductService(session)
    product = await service.create_product(
        lender_id=UUID(lender_id),
        name=data.name,
        description=data.description,
        tier=data.tier,
        min_amount=data.min_amount,
        max_amount=data.max_amount,
        min_installments=data.min_installments,
        max_installments=data.max_installments,
        annual_interest_rate=data.annual_interest_rate,
        example_amount=data.example_amount,
        example_monthly_payment=data.example_monthly_payment,
        is_active=data.is_active,
        is_featured=data.is_featured,
        sort_order=data.sort_order,
    )
    return _product_to_response(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_lender_product(
    product_id: UUID,
    data: ProductUpdate,
    current_user: User = Depends(require_roles("platform_admin", "owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Update a loan product."""
    service = LoanProductService(session)
    update_data = data.model_dump(exclude_unset=True)
    product = await service.update_product(
        product_id=product_id,
        lender_id=UUID(lender_id),
        **update_data,
    )
    return _product_to_response(product)


@router.delete("/{product_id}", status_code=204)
async def delete_lender_product(
    product_id: UUID,
    current_user: User = Depends(require_roles("platform_admin", "owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a loan product."""
    service = LoanProductService(session)
    await service.delete_product(product_id, UUID(lender_id))


@router.post("/{product_id}/toggle", response_model=ProductResponse)
async def toggle_product_active(
    product_id: UUID,
    current_user: User = Depends(require_roles("platform_admin", "owner", "manager")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Toggle the active status of a product."""
    service = LoanProductService(session)
    product = await service.toggle_active(product_id, UUID(lender_id))
    return _product_to_response(product)
