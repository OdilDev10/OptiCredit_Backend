"""Schemas for customer CRUD operations."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.core.enums import CustomerStatus


class CustomerBase(BaseModel):
    """Shared customer fields."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    document_type: str = Field(..., min_length=1, max_length=50)
    document_number: str = Field(..., min_length=1, max_length=50)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    phone: str = Field(..., min_length=1, max_length=20)
    email: EmailStr
    address_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default="DO", max_length=100)
    credit_limit: Decimal | None = Field(default=None, ge=0)


class CustomerCreate(BaseModel):
    """Payload for creating a customer from Flutter."""

    full_name: str = Field(..., min_length=2, max_length=200)
    document_type: str = Field(..., min_length=1, max_length=50)
    document_number: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=1, max_length=20)
    email: EmailStr
    credit_limit: Decimal | None = Field(default=None, ge=0)


class CustomerUpdate(BaseModel):
    """Payload for partially updating a customer."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    document_type: str | None = Field(default=None, min_length=1, max_length=50)
    document_number: str | None = Field(default=None, min_length=1, max_length=50)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, min_length=1, max_length=20)
    email: EmailStr | None = None
    address_line: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    status: CustomerStatus | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0)


class IdentityDocumentUpload(BaseModel):
    """Placeholder schema for future KYC uploads."""

    document_kind: str
    file_name: str
    mime_type: str


class CustomerRead(CustomerBase):
    """Serialized customer representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    lender_id: str
    user_id: str | None = None
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class PaginatedCustomerResponse(BaseModel):
    """Paginated response envelope for customers."""

    items: list[CustomerRead]
    total: int
    skip: int
    limit: int
