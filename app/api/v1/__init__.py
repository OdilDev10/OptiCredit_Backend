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

router = api_router

__all__ = ["api_router", "router"]
