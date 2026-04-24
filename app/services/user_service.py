"""Service for user management - CRUD, roles, invitations."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole, UserStatus
from app.core.exceptions import (
    ConflictException,
    ValidationException,
    NotFoundException,
)
from app.core.security import hash_password
from app.models.user import User
from app.models.lender import Lender
from app.repositories.user_repo import UserRepository
from app.services.email_service import email_service
from app.services.notifications import NotificationDispatcher


class UserService:
    """Service for user operations within a lender context."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def create_user(
        self,
        lender_id: UUID,
        email: str,
        first_name: str,
        last_name: str,
        role: UserRole = UserRole.AGENT,
        password: str | None = None,
        phone: str | None = None,
        set_inactive: bool = False,
    ) -> User:
        """
        Create a new user in a lender organization.

        Args:
            lender_id: Parent lender ID
            email: User email (must be unique)
            first_name: First name
            last_name: Last name
            role: User role (default: AGENT)
            password: Password (if provided, user starts as ACTIVE)
            phone: Phone number
            set_inactive: If True, user starts as INACTIVE (requires email verification)

        Returns:
            Created User

        Raises:
            ConflictException: If email already exists
            ValidationException: If invalid input
        """
        email = email.lower().strip()

        if not email or "@" not in email:
            raise ValidationException("Valid email is required")

        if not first_name or len(first_name) < 2:
            raise ValidationException("First name must be at least 2 characters")

        if not last_name or len(last_name) < 2:
            raise ValidationException("Last name must be at least 2 characters")

        # Check email uniqueness
        if await self.user_repo.email_exists(email):
            raise ConflictException(
                f"User with email {email} already exists",
                code="EMAIL_ALREADY_EXISTS",
            )

        # Determine password and status
        password_hash = hash_password(password) if password else ""
        status = UserStatus.INACTIVE if set_inactive else UserStatus.ACTIVE

        user = User(
            lender_id=lender_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            password_hash=password_hash,
            role=role,
            status=status,
        )

        self.session.add(user)
        await self.session.flush()

        try:
            dispatcher = NotificationDispatcher(self.session)
            lender = await self.session.get(Lender, lender_id) if lender_id else None
            lender_name = (
                lender.commercial_name
                if lender and lender.commercial_name
                else "OptiCredit"
            )
            await dispatcher.notify_user_created(
                user_id=user.id,
                lender_name=lender_name,
            )
        except Exception:
            pass

        return user

    async def get_user(self, user_id: UUID) -> User:
        """Get user by ID."""
        return await self.user_repo.get_or_404(user_id, error_code="USER_NOT_FOUND")

    async def get_user_by_email(self, email: str) -> User:
        """Get user by email."""
        user = await self.user_repo.get_by_email(email.lower().strip())
        if not user:
            raise NotFoundException("User not found", code="USER_NOT_FOUND")
        return user

    async def get_lender_users(self, lender_id: UUID) -> list[User]:
        """Get all users in a lender organization."""
        return await self.user_repo.get_by_lender(lender_id)

    async def update_user_role(self, user_id: UUID, new_role: UserRole) -> User:
        """Change user role."""
        user = await self.get_user(user_id)

        if user.role == new_role:
            raise ValidationException("User already has this role")

        user.role = new_role
        await self.session.flush()

        return user

    async def update_user_status(self, user_id: UUID, new_status: UserStatus) -> User:
        """Change user status (active, inactive, blocked)."""
        user = await self.get_user(user_id)

        if user.status == new_status:
            raise ValidationException(f"User is already {new_status.value}")

        user.status = new_status
        await self.session.flush()

        return user

    async def activate_user(self, user_id: UUID) -> User:
        """Activate an inactive user."""
        user = await self.update_user_status(user_id, UserStatus.ACTIVE)
        try:
            dispatcher = NotificationDispatcher(self.session)
            await dispatcher.notify_user_enabled(user_id)
        except Exception:
            pass
        return user

    async def deactivate_user(self, user_id: UUID) -> User:
        """Deactivate (block) a user."""
        user = await self.update_user_status(user_id, UserStatus.BLOCKED)
        try:
            dispatcher = NotificationDispatcher(self.session)
            await dispatcher.notify_user_disabled(user_id)
        except Exception:
            pass
        return user

    async def update_last_login(self, user_id: UUID) -> User:
        """Update last login timestamp."""
        user = await self.get_user(user_id)
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()
        return user

    async def send_user_invitation(
        self,
        email: str,
        first_name: str,
        last_name: str,
        lender_name: str,
        invitation_link: str,
    ) -> dict:
        """
        Send invitation email to a new user.

        Args:
            email: Recipient email
            first_name: User first name
            last_name: User last name
            lender_name: Lender name for context
            invitation_link: Link with token to accept invitation

        Returns:
            dict with success status
        """
        try:
            subject = f"Invitación a {lender_name}"
            body = f"""
Hola {first_name} {last_name},

Fuiste invitado a unirte a {lender_name} en nuestra plataforma de gestión de préstamos.

Haz clic en el siguiente enlace para aceptar tu invitación:
{invitation_link}

Este enlace expira en 7 días.

Si no solicitaste esta invitación, puedes ignorar este correo.

Saludos,
El equipo de Préstamos
            """.strip()

            await email_service.send_email(
                to_email=email,
                subject=subject,
                body=body,
            )

            return {
                "success": True,
                "message": f"Invitation sent to {email}",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def change_password(self, user_id: UUID, new_password: str) -> User:
        """Change user password."""
        if len(new_password) < 8:
            raise ValidationException("Password must be at least 8 characters")

        user = await self.get_user(user_id)
        user.password_hash = hash_password(new_password)
        await self.session.flush()

        return user

    async def get_users_by_role(self, lender_id: UUID, role: UserRole) -> list[User]:
        """Get all users with a specific role in a lender."""
        return await self.user_repo.get_by_lender_and_role(lender_id, role)

    async def get_platform_admins(self) -> list[User]:
        """Get all platform admins (lender_id is None)."""
        return await self.user_repo.get_platform_admins()
