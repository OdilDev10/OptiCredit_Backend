"""Support endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.dependencies import require_roles
from app.models.support_request import SupportRequest
from app.models.user import User
from app.services.email_service import email_service


router = APIRouter(prefix="/support", tags=["support"])


class SupportContactRequest(BaseModel):
    """Payload for support contact form."""

    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    message: str = Field(..., min_length=5, max_length=5000)
    source: str | None = Field(default="site_footer", max_length=120)


class SupportContactResponse(BaseModel):
    """API response for support contact submissions."""

    success: bool
    message: str
    request_id: str


class SupportRequestListItem(BaseModel):
    id: str
    name: str
    email: str
    message: str
    status: str
    source: str | None
    user_id: str | None
    created_at: datetime | None
    updated_at: datetime | None


class SupportRequestListResponse(BaseModel):
    items: list[SupportRequestListItem]
    total: int
    skip: int
    limit: int


class SupportStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(new|in_review|resolved|closed)$")


class SupportStatusUpdateResponse(BaseModel):
    success: bool
    message: str
    item: SupportRequestListItem


@router.post("/contact", response_model=SupportContactResponse)
async def submit_support_contact(
    payload: SupportContactRequest,
    session: AsyncSession = Depends(get_db),
) -> SupportContactResponse:
    """Store and notify a support request from public website."""
    request_row = SupportRequest(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        message=payload.message.strip(),
        source=payload.source,
        status="new",
    )
    session.add(request_row)
    await session.commit()
    await session.refresh(request_row)

    inbox = settings.support_inbox_email
    if inbox:
        subject = f"[Soporte] Nueva solicitud de {request_row.name}"
        body = (
            "Nueva solicitud de soporte\n\n"
            f"Nombre: {request_row.name}\n"
            f"Email: {request_row.email}\n"
            f"Origen: {request_row.source or 'n/a'}\n"
            f"ID: {request_row.id}\n\n"
            "Mensaje:\n"
            f"{request_row.message}\n"
        )
        await email_service.send_email(inbox, subject, body)

    return SupportContactResponse(
        success=True,
        message="Hemos recibido tu solicitud. Te contactaremos pronto.",
        request_id=str(request_row.id),
    )


@router.get("/requests", response_model=SupportRequestListResponse)
async def list_support_requests(
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
    status: str | None = None,
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> SupportRequestListResponse:
    """Admin list of support requests with filters."""
    filters = []

    if status:
        filters.append(SupportRequest.status == status)

    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                SupportRequest.name.ilike(term),
                SupportRequest.email.ilike(term),
                SupportRequest.message.ilike(term),
            )
        )

    count_stmt = select(func.count(SupportRequest.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await session.execute(count_stmt)).scalar() or 0

    list_stmt = select(SupportRequest).order_by(SupportRequest.created_at.desc())
    if filters:
        list_stmt = list_stmt.where(*filters)
    list_stmt = list_stmt.offset(skip).limit(limit)

    rows = (await session.execute(list_stmt)).scalars().all()
    items = [
        SupportRequestListItem(
            id=str(row.id),
            name=row.name,
            email=row.email,
            message=row.message,
            status=row.status,
            source=row.source,
            user_id=str(row.user_id) if row.user_id else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    return SupportRequestListResponse(items=items, total=total, skip=skip, limit=limit)


@router.patch("/requests/{request_id}/status", response_model=SupportStatusUpdateResponse)
async def update_support_request_status(
    request_id: UUID,
    payload: SupportStatusUpdateRequest,
    _: User = Depends(require_roles("platform_admin")),
    session: AsyncSession = Depends(get_db),
) -> SupportStatusUpdateResponse:
    """Admin update status for a support request."""
    row = await session.get(SupportRequest, request_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada.",
        )

    row.status = payload.status
    session.add(row)
    await session.commit()
    await session.refresh(row)

    return SupportStatusUpdateResponse(
        success=True,
        message="Estado actualizado correctamente.",
        item=SupportRequestListItem(
            id=str(row.id),
            name=row.name,
            email=row.email,
            message=row.message,
            status=row.status,
            source=row.source,
            user_id=str(row.user_id) if row.user_id else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        ),
    )
