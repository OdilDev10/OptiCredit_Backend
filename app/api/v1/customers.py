"""Customer endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_lender_context, require_roles
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate, PaginatedCustomerResponse
from app.services.customer_service import CustomerService


router = APIRouter(prefix="/customers", tags=["customers"])


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) < 2:
        return parts[0], "Cliente"
    return parts[0], " ".join(parts[1:])


@router.get("", response_model=PaginatedCustomerResponse)
async def list_customers(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_roles("owner", "manager", "agent", "reviewer")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> PaginatedCustomerResponse:
    """List customers for the authenticated lender."""
    service = CustomerService(session)
    customers = await service.get_lender_customers(UUID(lender_id))
    paginated = customers[skip: skip + limit]
    return PaginatedCustomerResponse(
        items=[CustomerRead.model_validate(customer) for customer in paginated],
        total=len(customers),
        skip=skip,
        limit=limit,
    )


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(
    customer_id: UUID,
    _: User = Depends(require_roles("owner", "manager", "agent", "reviewer")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> CustomerRead:
    """Return a single customer scoped to the authenticated lender."""
    service = CustomerService(session)
    customer = await service.get_customer(customer_id)
    if str(customer.lender_id) != lender_id:
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("You do not have permission to access this customer")
    return CustomerRead.model_validate(customer)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    _: User = Depends(require_roles("owner", "manager", "agent")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> CustomerRead:
    """Create a customer under the authenticated lender."""
    first_name, last_name = _split_full_name(payload.full_name)
    service = CustomerService(session)
    customer = await service.create_customer(
        lender_id=UUID(lender_id),
        first_name=first_name,
        last_name=last_name,
        document_type=payload.document_type,
        document_number=payload.document_number,
        phone=payload.phone,
        email=payload.email,
        credit_limit=float(payload.credit_limit) if payload.credit_limit is not None else None,
    )
    await session.commit()
    await session.refresh(customer)
    return CustomerRead.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    _: User = Depends(require_roles("owner", "manager", "agent")),
    lender_id: str = Depends(get_lender_context),
    session: AsyncSession = Depends(get_db),
) -> CustomerRead:
    """Update a customer under the authenticated lender."""
    service = CustomerService(session)
    customer = await service.get_customer(customer_id)
    if str(customer.lender_id) != lender_id:
        from app.core.exceptions import ForbiddenException
        raise ForbiddenException("You do not have permission to update this customer")

    updated = await service.update_customer_profile(
        customer_id,
        **payload.model_dump(exclude_unset=True),
    )
    await session.commit()
    await session.refresh(updated)
    return CustomerRead.model_validate(updated)
