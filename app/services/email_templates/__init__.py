"""Email templates for OptiCredit."""

from app.services.email_templates.base import render_template, BASE_TEMPLATE
from app.services.email_templates.verification import get_verification_email_html
from app.services.email_templates.password_reset import get_password_reset_email_html
from app.services.email_templates.otp import get_otp_email_html
from app.services.email_templates.welcome import get_welcome_email_html
from app.services.email_templates.application import (
    get_application_submitted_email_html,
    get_application_approved_email_html,
    get_application_rejected_email_html,
)
from app.services.email_templates.payment import (
    get_payment_approved_email_html,
    get_payment_rejected_email_html,
    get_payment_pending_review_email_html,
    get_payment_received_email_html,
)
from app.services.email_templates.security import (
    get_password_changed_email_html,
    get_new_login_email_html,
    get_security_alert_email_html,
)

__all__ = [
    "render_template",
    "BASE_TEMPLATE",
    # Auth
    "get_verification_email_html",
    "get_password_reset_email_html",
    "get_otp_email_html",
    "get_welcome_email_html",
    # Application
    "get_application_submitted_email_html",
    "get_application_approved_email_html",
    "get_application_rejected_email_html",
    # Payment
    "get_payment_approved_email_html",
    "get_payment_rejected_email_html",
    "get_payment_pending_review_email_html",
    "get_payment_received_email_html",
    # Security
    "get_password_changed_email_html",
    "get_new_login_email_html",
    "get_security_alert_email_html",
]
