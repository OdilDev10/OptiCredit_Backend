"""SQLAlchemy declarative base configuration."""

from app.db.base_class import Base

# Import models so SQLAlchemy metadata is populated before migrations/startup.
from app.models.auth import EmailVerification, OTP, PasswordReset  # noqa: E402,F401
from app.models.lender import Lender, LenderBankAccount, LenderInvitation  # noqa: E402,F401
from app.models.user import User  # noqa: E402,F401
from app.models.customer import Customer  # noqa: E402,F401
from app.models.loan_application import LoanApplication  # noqa: E402,F401
from app.models.loan import Loan, Disbursement, Installment  # noqa: E402,F401
from app.models.payment import Payment, Voucher, OcrResult, PaymentMatch  # noqa: E402,F401
from app.models.subscription import Subscription  # noqa: E402,F401
