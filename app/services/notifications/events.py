"""Notification events - all possible notification types in the system."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID


class NotificationEventType(str, Enum):
    APPLICATION_SUBMITTED = "application_submitted"
    APPLICATION_APPROVED = "application_approved"
    APPLICATION_REJECTED = "application_rejected"

    PAYMENT_SUBMITTED = "payment_submitted"
    PAYMENT_APPROVED = "payment_approved"
    PAYMENT_REJECTED = "payment_rejected"

    USER_CREATED = "user_created"
    USER_DISABLED = "user_disabled"
    USER_ENABLED = "user_enabled"
    USER_ROLE_CHANGED = "user_role_changed"

    LENDER_REGISTERED = "lender_registered"
    LENDER_APPROVED = "lender_approved"
    LENDER_REJECTED = "lender_rejected"

    LOAN_DISBURSED = "loan_disbursed"
    INSTALLMENT_OVERDUE = "installment_overdue"

    PASSWORD_CHANGED = "password_changed"
    NEW_LOGIN = "new_login"


@dataclass
class NotificationEvent:
    """A notification event to be dispatched."""

    event_type: NotificationEventType
    recipient_id: UUID
    actor_name: Optional[str] = None
    lender_name: Optional[str] = None
    amount: Optional[float] = None
    loan_number: Optional[str] = None
    installment_number: Optional[int] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    device_info: Optional[str] = None
    extra_data: Optional[dict] = None


@dataclass
class NotificationRecipient:
    """A notification recipient."""

    user_id: UUID
    email: str
    full_name: str
    role: str
