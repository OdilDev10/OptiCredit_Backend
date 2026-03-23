"""Import all models for Alembic migration generation."""

from app.models.base_model import BaseModel
from app.models.lender import Lender, LenderInvitation, LenderBankAccount
from app.models.user import User
from app.models.customer import Customer
from app.models.auth import EmailVerification, PasswordReset, OTP
from app.models.loan_application import LoanApplication
from app.models.loan import Loan, Disbursement, Installment
from app.models.payment import Payment, Voucher, OcrResult, PaymentMatch

__all__ = [
    "BaseModel",
    "Lender",
    "LenderInvitation",
    "LenderBankAccount",
    "User",
    "Customer",
    "EmailVerification",
    "PasswordReset",
    "OTP",
    "LoanApplication",
    "Loan",
    "Disbursement",
    "Installment",
    "Payment",
    "Voucher",
    "OcrResult",
    "PaymentMatch",
]
