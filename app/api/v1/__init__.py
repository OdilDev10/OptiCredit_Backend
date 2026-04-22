"""API v1 router registry."""

from fastapi import APIRouter

from app.api.v1.app_config import router as app_config_router
from app.api.v1.auth import router as auth_router
from app.api.v1.lenders import router as lenders_router
from app.api.v1.users import router as users_router
from app.api.v1.braintree_webhook import router as braintree_router
from app.api.v1.files import router as files_router
from app.api.v1.loan_applications import router as loan_applications_router
from app.api.v1.loans import router as loans_router
from app.api.v1.payments import router as payments_router
from app.api.v1.customers import router as customers_router
from app.api.v1.me import router as me_router
from app.api.v1.reports import router as reports_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.subscriptions import router as subscriptions_router
from app.api.v1.lender import router as lender_router
from app.api.v1.admin import router as admin_router
from app.api.v1.plans import router as plans_router
from app.api.v1.admin_reports import router as admin_reports_router
from app.api.v1.admin_system import router as admin_system_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.lender_settings import router as lender_settings_router
from app.api.v1.client_settings import router as client_settings_router
from app.api.v1.loan_products import router as loan_products_router
from app.api.v1.lender_products import router as lender_products_router
from app.api.v1.payment_with_voucher import router as payment_with_voucher_router
from app.api.v1.support import router as support_router
from app.api.v1.audit_logs import router as audit_logs_router


api_router = APIRouter()
api_router.include_router(app_config_router)
api_router.include_router(auth_router)
api_router.include_router(lenders_router)
api_router.include_router(users_router)
api_router.include_router(braintree_router)
api_router.include_router(files_router)
api_router.include_router(loan_applications_router)
api_router.include_router(loans_router)
api_router.include_router(payments_router)
api_router.include_router(customers_router)
api_router.include_router(me_router)
api_router.include_router(reports_router)
api_router.include_router(notifications_router)
api_router.include_router(subscriptions_router)
api_router.include_router(lender_router)
api_router.include_router(admin_router)
api_router.include_router(plans_router)
api_router.include_router(admin_reports_router)
api_router.include_router(admin_system_router)
api_router.include_router(admin_users_router)
api_router.include_router(lender_settings_router)
api_router.include_router(client_settings_router)
api_router.include_router(loan_products_router)
api_router.include_router(lender_products_router)
api_router.include_router(payment_with_voucher_router)
api_router.include_router(support_router)
api_router.include_router(audit_logs_router)

router = api_router

__all__ = ["api_router", "router"]
