"""Authentication service with login, register, password reset, OTP logic."""

from uuid import uuid4
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import UserRepository
from app.repositories.customer_repo import CustomerRepository
from app.repositories.lender_repo import LenderRepository
from app.repositories.email_verification_repo import EmailVerificationRepository
from app.repositories.password_reset_repo import PasswordResetRepository
from app.repositories.otp_repo import OTPRepository
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.exceptions import (
    UnauthorizedException,
    ConflictException,
    ValidationException,
    NotFoundException,
)
from app.core.enums import AccountType, UserRole
from app.core.permissions import get_permissions_for_role
from app.services.email_service import email_service
from app.services.token_blacklist import token_blacklist
from app.config import settings
import random
import string


class AuthService:
    """Service for authentication operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.lender_repo = LenderRepository(session)
        self.email_verification_repo = EmailVerificationRepository(session)
        self.password_reset_repo = PasswordResetRepository(session)
        self.otp_repo = OTPRepository(session)

    @staticmethod
    def _build_access_claims(user) -> dict:
        """Build rich access-token claims for frontend authorization."""
        role_value = getattr(user.role, "value", user.role)
        account_type_value = getattr(user.account_type, "value", user.account_type)
        status_value = getattr(user.status, "value", user.status)
        permissions = get_permissions_for_role(role_value)

        return {
            "sub": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": role_value,
            "roles": [role_value],
            "permissions": permissions,
            "account_type": account_type_value,
            "status": status_value,
            "lender_id": str(user.lender_id) if user.lender_id else None,
            "phone": user.phone,
        }

    async def register(
        self, email: str, password: str, first_name: str, last_name: str
    ) -> dict:
        """Register new user with email verification."""
        email = email.lower().strip()

        # Validate password
        if len(password) < 8:
            raise ValidationException("Password must be at least 8 characters")

        # Check if email already exists
        if await self.user_repo.email_exists(email):
            raise ConflictException(
                f"Email {email} is already registered", code="EMAIL_ALREADY_EXISTS"
            )

        # Create unverified user
        user = await self.user_repo.create_user(
            email=email,
            password_hash=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            account_type=AccountType.INTERNAL,
            status="inactive",  # User is inactive until email is verified
        )

        # Generate email verification token
        token = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=24)

        await self.email_verification_repo.create(
            {
                "user_id": user.id,
                "token": token,
                "expires_at": expires_at,
            }
        )

        # Send verification email
        await email_service.send_verification_email(
            to_email=email, token=token, recipient_name=f"{first_name} {last_name}"
        )

        return {
            "user_id": str(user.id),
            "email": user.email,
            "status": "pending_verification",
            "message": "Verification email sent. Check your inbox.",
        }

    async def verify_email(self, token: str) -> dict:
        """Verify email with token."""
        # Get verification record
        verification = await self.email_verification_repo.get_by_token(token)
        if not verification:
            raise NotFoundException(
                "Verification token is invalid or expired", code="INVALID_TOKEN"
            )

        # Check if expired
        if verification.expires_at < datetime.utcnow():
            raise ValidationException(
                "Verification token has expired", code="TOKEN_EXPIRED"
            )

        # Check if already verified
        if verification.verified_at:
            raise ValidationException("Email already verified", code="ALREADY_VERIFIED")

        # Mark as verified
        verification.verified_at = datetime.utcnow()
        await self.email_verification_repo.update(
            verification, {"verified_at": datetime.utcnow()}
        )

        # Activate user
        user = await self.user_repo.get_or_404(verification.user_id)
        await self.user_repo.update(user, {"status": "active"})

        await self.session.commit()

        return {
            "email": user.email,
            "status": "verified",
            "message": "Email verified successfully. You can now login.",
        }

    async def login(self, email: str, password: str) -> dict:
        """Login user and return access token."""
        email = email.lower().strip()

        # Get user
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise UnauthorizedException("Invalid email or password")

        # Check if user is active
        if user.status != "active":
            raise UnauthorizedException(
                "User account is not active. Please verify your email.",
                code="USER_INACTIVE",
            )

        # Verify password
        if not verify_password(password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")

        # Update last login
        await self.user_repo.update(user, {"last_login_at": datetime.now(timezone.utc)})

        # Create tokens
        access_token = create_access_token(self._build_access_claims(user))

        refresh_token, token_id = create_refresh_token(
            {
                "sub": str(user.id),
                "type": "refresh",
            }
        )

        # Register refresh token for rotation tracking
        from datetime import timedelta

        exp = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
        token_blacklist.register_token(str(user.id), refresh_token, exp)

        await self.session.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": getattr(user.role, "value", user.role),
                "account_type": getattr(user.account_type, "value", user.account_type),
                "status": getattr(user.status, "value", user.status),
                "lender_id": str(user.lender_id) if user.lender_id else None,
                "phone": user.phone,
                "roles": [getattr(user.role, "value", user.role)],
                "permissions": get_permissions_for_role(
                    getattr(user.role, "value", user.role)
                ),
            },
        }

    async def refresh_token_service(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token with rotation."""
        # Check if token is blacklisted
        if token_blacklist.is_blacklisted(refresh_token):
            raise UnauthorizedException("Token has been revoked")

        # Decode refresh token
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid refresh token")

        # Get user
        user = await self.user_repo.get_or_404(user_id)

        # Rotate token: blacklist old refresh token
        token_blacklist.blacklist_token(refresh_token)

        # Create new access token
        access_token = create_access_token(self._build_access_claims(user))

        # Create new refresh token
        new_refresh_token, new_token_id = create_refresh_token(
            {
                "sub": str(user.id),
                "type": "refresh",
            }
        )

        # Register new refresh token
        from datetime import timedelta

        exp = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
        token_blacklist.register_token(str(user.id), new_refresh_token, exp)

        await self.session.commit()

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }

    async def logout_all(self, user_id: str) -> dict:
        """Logout from all devices - invalidate all refresh tokens for user."""
        count = token_blacklist.revoke_all_user_tokens(user_id)
        return {
            "message": f"Logged out from all devices",
            "revoked_sessions": count,
        }

    async def logout(self, user_id: str, refresh_token: str) -> dict:
        """Logout - invalidate the current refresh token."""
        token_blacklist.blacklist_token(refresh_token)
        return {
            "message": "Logged out successfully",
        }

    async def forgot_password(self, email: str) -> dict:
        """Request password reset."""
        email = email.lower().strip()

        # Get user
        user = await self.user_repo.get_by_email(email)
        if not user:
            # For security, don't reveal if email exists
            return {
                "message": "If email exists, a password reset link has been sent.",
            }

        # Generate reset token
        token = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=1)

        await self.password_reset_repo.create(
            {
                "user_id": user.id,
                "token": token,
                "expires_at": expires_at,
            }
        )

        # Send reset email
        await email_service.send_password_reset_email(
            to_email=email,
            token=token,
            recipient_name=f"{user.first_name} {user.last_name}",
        )

        await self.session.commit()

        return {
            "message": "If email exists, a password reset link has been sent.",
        }

    async def verify_reset_token(self, token: str) -> dict:
        """Verify that reset token is valid."""
        reset = await self.password_reset_repo.get_by_token(token)
        if not reset:
            raise NotFoundException(
                "Reset token is invalid or expired", code="INVALID_TOKEN"
            )

        # Check if expired
        if reset.expires_at < datetime.utcnow():
            raise ValidationException("Reset token has expired", code="TOKEN_EXPIRED")

        # Check if already used
        if reset.used_at:
            raise ValidationException("Reset token already used", code="TOKEN_USED")

        return {
            "valid": True,
            "message": "Token is valid. You can now reset your password.",
        }

    async def reset_password(self, token: str, new_password: str) -> dict:
        """Reset password with token."""
        # Validate password
        if len(new_password) < 8:
            raise ValidationException("Password must be at least 8 characters")

        # Get reset record
        reset = await self.password_reset_repo.get_by_token(token)
        if not reset:
            raise NotFoundException(
                "Reset token is invalid or expired", code="INVALID_TOKEN"
            )

        # Check if expired
        if reset.expires_at < datetime.utcnow():
            raise ValidationException("Reset token has expired", code="TOKEN_EXPIRED")

        # Check if already used
        if reset.used_at:
            raise ValidationException("Reset token already used", code="TOKEN_USED")

        # Get user and update password
        user = await self.user_repo.get_or_404(reset.user_id)
        await self.user_repo.update(
            user, {"password_hash": hash_password(new_password)}
        )

        # Mark token as used
        await self.password_reset_repo.update(reset, {"used_at": datetime.utcnow()})

        await self.session.commit()

        return {
            "email": user.email,
            "message": "Password reset successfully. You can now login with your new password.",
        }

    async def send_otp(self, user_id: str) -> dict:
        """Generate and send OTP to user."""
        # Generate OTP code
        otp_code = "".join(random.choices(string.digits, k=6))
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        # Get user
        user = await self.user_repo.get_or_404(user_id)

        # Create OTP record
        await self.otp_repo.create(
            {
                "user_id": user_id,
                "code": otp_code,
                "expires_at": expires_at,
                "attempts": 0,
            }
        )

        # Send OTP email
        await email_service.send_otp_email(
            to_email=user.email,
            otp_code=otp_code,
            recipient_name=f"{user.first_name} {user.last_name}",
        )

        await self.session.commit()

        return {
            "message": "OTP sent to your email",
        }

    async def verify_otp(self, user_id: str, otp_code: str) -> dict:
        """Verify OTP code."""
        # Get latest OTP for user
        otp = await self.otp_repo.get_latest_by_user(user_id)
        if not otp:
            raise NotFoundException("No OTP found", code="NO_OTP")

        # Check if expired
        if otp.expires_at < datetime.utcnow():
            raise ValidationException("OTP has expired", code="OTP_EXPIRED")

        # Check if already verified
        if otp.verified_at:
            raise ValidationException(
                "OTP already verified", code="OTP_ALREADY_VERIFIED"
            )

        # Check if code matches
        if otp.code != otp_code.strip():
            otp.attempts += 1
            if otp.attempts >= 3:
                raise ValidationException("Too many attempts", code="TOO_MANY_ATTEMPTS")
            await self.otp_repo.update(otp, {"attempts": otp.attempts})
            await self.session.commit()
            raise ValidationException("Incorrect OTP code", code="INVALID_OTP")

        # Mark as verified
        await self.otp_repo.update(otp, {"verified_at": datetime.utcnow()})

        await self.session.commit()

        return {
            "message": "OTP verified successfully",
        }

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> dict:
        """Change password for authenticated user."""
        # Validate passwords
        if len(new_password) < 8:
            raise ValidationException("New password must be at least 8 characters")

        if current_password == new_password:
            raise ValidationException(
                "New password must be different from current password"
            )

        # Get user
        user = await self.user_repo.get_or_404(user_id)

        # Verify current password
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedException("Current password is incorrect")

        # Update password
        await self.user_repo.update(
            user, {"password_hash": hash_password(new_password)}
        )

        await self.session.commit()

        return {
            "message": "Password changed successfully",
        }

    async def register_customer(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        lender_id: str,
        document_type: str,
        document_number: str,
        phone: str,
    ) -> dict:
        """Register new customer (cliente that borrows money)."""
        email = email.lower().strip()
        document_number = document_number.strip()

        # Validate inputs
        if len(password) < 8:
            raise ValidationException("Password must be at least 8 characters")

        if not first_name or len(first_name) < 2:
            raise ValidationException("First name must be at least 2 characters")

        if not last_name or len(last_name) < 2:
            raise ValidationException("Last name must be at least 2 characters")

        # Check if customer already exists
        existing_customer = await self.customer_repo.get_by_email(email)
        if existing_customer:
            raise ConflictException(
                f"Customer with email {email} already exists",
                code="EMAIL_ALREADY_EXISTS",
            )

        if await self.customer_repo.document_exists(document_number):
            raise ConflictException(
                f"Customer with document {document_number} already exists",
                code="DOCUMENT_EXISTS",
            )

        # Create customer record
        customer = await self.customer_repo.create(
            {
                "lender_id": lender_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "document_type": document_type,
                "document_number": document_number,
                "status": "active",  # Customers start as active
            }
        )

        # Generate verification token for email
        token = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=24)

        await self.email_verification_repo.create(
            {
                "user_id": None,  # We'll link to user if customer creates account
                "token": token,
                "expires_at": expires_at,
            }
        )

        # Send verification email
        await email_service.send_verification_email(
            to_email=email, token=token, recipient_name=f"{first_name} {last_name}"
        )

        await self.session.commit()

        return {
            "customer_id": str(customer.id),
            "email": customer.email,
            "status": "pending_verification",
            "message": "Verification email sent. Check your inbox.",
        }

    async def register_lender(
        self,
        email: str,
        password: str,
        legal_name: str,
        lender_type: str,
        document_type: str,
        document_number: str,
        phone: str,
        commercial_name: str | None = None,
    ) -> dict:
        """Register new lender (prestamista/financiera)."""
        email = email.lower().strip()
        document_number = document_number.strip()

        # Validate inputs
        if len(password) < 8:
            raise ValidationException("Password must be at least 8 characters")

        if not legal_name or len(legal_name) < 3:
            raise ValidationException("Legal name must be at least 3 characters")

        if lender_type not in ["financial", "individual"]:
            raise ValidationException("Lender type must be 'financial' or 'individual'")

        # Validate document based on lender type
        if lender_type == "individual":
            if document_type.lower() != "cedula":
                raise ValidationException(
                    "Individual lenders must provide 'Cedula' as document type"
                )
        else:  # financial
            if document_type.lower() not in ["rnc", "cedula"]:
                raise ValidationException(
                    "Financial lenders must provide 'RNC' or 'Cedula' as document type"
                )

        # Check if lender already exists
        if await self.lender_repo.get_by_email(email):
            raise ConflictException(
                f"Lender with email {email} already exists",
                code="EMAIL_ALREADY_EXISTS",
            )

        if await self.lender_repo.get_by_document_number(document_number):
            raise ConflictException(
                f"Lender with document {document_number} already exists",
                code="DOCUMENT_EXISTS",
            )

        # Create lender
        lender = await self.lender_repo.create(
            {
                "legal_name": legal_name,
                "commercial_name": commercial_name or legal_name,
                "lender_type": lender_type,
                "document_type": document_type,
                "document_number": document_number,
                "email": email,
                "phone": phone,
                "status": "pending",  # Lenders start as pending
            }
        )

        # Create owner user for the lender
        owner_user = await self.user_repo.create_user(
            email=email,
            password_hash=hash_password(password),
            first_name=legal_name.split()[0],
            last_name=" ".join(legal_name.split()[1:])
            if len(legal_name.split()) > 1
            else "Owner",
            role=UserRole.OWNER,
            account_type=AccountType.LENDER,
            lender_id=lender.id,
        )

        # Send verification email to lender
        token = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=24)

        await self.email_verification_repo.create(
            {
                "user_id": owner_user.id,
                "token": token,
                "expires_at": expires_at,
            }
        )

        await email_service.send_verification_email(
            to_email=email,
            token=token,
            recipient_name=f"{owner_user.first_name} {owner_user.last_name}",
        )

        await self.session.commit()

        return {
            "lender_id": str(lender.id),
            "user_id": str(owner_user.id),
            "email": email,
            "status": "pending_verification",
            "message": "Verification email sent. Check your inbox to activate your lender account.",
        }
