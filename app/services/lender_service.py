"""Service for lender business logic - registration, activation, invitations."""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LenderStatus, UserRole
from app.core.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.models.lender import Lender, LenderInvitation, LenderBankAccount
from app.models.user import User
from app.repositories.lender_repo import (
    LenderRepository,
    LenderInvitationRepository,
    LenderBankAccountRepository,
)
from app.repositories.user_repo import UserRepository
from app.services.notifications import NotificationDispatcher


class LenderService:
    """Service for lender operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.lender_repo = LenderRepository(session)
        self.invitation_repo = LenderInvitationRepository(session)
        self.bank_account_repo = LenderBankAccountRepository(session)

    async def register_lender(
        self,
        legal_name: str,
        commercial_name: str,
        lender_type: str,
        document_type: str,
        document_number: str,
        email: str,
        phone: str,
    ) -> Lender:
        """
        Register a new lender.

        Args:
            legal_name: Legal name of the lender
            commercial_name: Commercial/display name
            lender_type: "financial" or "individual"
            document_type: Type of document (RNC, DPI, etc)
            document_number: Document number (must be unique)
            email: Contact email
            phone: Contact phone

        Returns:
            Created Lender with status PENDING

        Raises:
            ConflictException: If email or document already exists
            ValidationException: If invalid input
        """
        # Validate input
        email = email.lower().strip()
        document_number = document_number.strip()

        if not legal_name or len(legal_name) < 3:
            raise ValidationException("Legal name must be at least 3 characters")

        if not email or "@" not in email:
            raise ValidationException("Valid email is required")

        if not document_number:
            raise ValidationException("Document number is required")

        # Check for existing lender
        if await self.lender_repo.exists_with_identity(
            email=email,
            document_number=document_number,
        ):
            raise ConflictException(
                "A lender with this email or document number already exists",
                code="LENDER_EXISTS",
            )

        # Create lender (starts in PENDING status)
        lender = Lender(
            legal_name=legal_name,
            commercial_name=commercial_name or legal_name,
            lender_type=lender_type,
            document_type=document_type,
            document_number=document_number,
            email=email,
            phone=phone,
            status=LenderStatus.PENDING,
        )

        self.session.add(lender)
        await self.session.flush()

        try:
            user_repo = UserRepository(self.session)
            platform_admins = await user_repo.get_platform_admins()
            if platform_admins:
                dispatcher = NotificationDispatcher(self.session)
                await dispatcher.notify_lender_registered(
                    platform_admin_ids=[admin.id for admin in platform_admins],
                    lender_name=commercial_name or legal_name,
                )
        except Exception:
            pass

        return lender

    async def activate_lender(self, lender_id: UUID) -> Lender:
        """Activate a lender (change status from PENDING to ACTIVE)."""
        lender = await self.lender_repo.get_or_404(
            lender_id, error_code="LENDER_NOT_FOUND"
        )

        if lender.status == LenderStatus.ACTIVE:
            raise ValidationException("Lender is already active")

        lender.status = LenderStatus.ACTIVE
        await self.session.flush()

        try:
            user_repo = UserRepository(self.session)
            owners = await user_repo.get_by_lender_and_role(lender_id, UserRole.OWNER)
            if owners:
                dispatcher = NotificationDispatcher(self.session)
                for owner in owners:
                    await dispatcher.notify_lender_approved(
                        lender_owner_user_id=owner.id,
                        lender_name=lender.commercial_name or lender.legal_name,
                    )
        except Exception:
            pass

        return lender

    async def suspend_lender(
        self, lender_id: UUID, reason: str | None = None
    ) -> Lender:
        """Suspend a lender (change status to SUSPENDED)."""
        lender = await self.lender_repo.get_or_404(
            lender_id, error_code="LENDER_NOT_FOUND"
        )

        if lender.status == LenderStatus.SUSPENDED:
            raise ValidationException("Lender is already suspended")

        lender.status = LenderStatus.SUSPENDED
        await self.session.flush()

        return lender

    async def reject_lender(self, lender_id: UUID, reason: str | None = None) -> Lender:
        """Reject a lender application (change status to REJECTED)."""
        lender = await self.lender_repo.get_or_404(
            lender_id, error_code="LENDER_NOT_FOUND"
        )

        if lender.status == LenderStatus.REJECTED:
            raise ValidationException("Lender is already rejected")

        lender.status = LenderStatus.REJECTED
        await self.session.flush()

        try:
            user_repo = UserRepository(self.session)
            owners = await user_repo.get_by_lender_and_role(lender_id, UserRole.OWNER)
            if owners:
                dispatcher = NotificationDispatcher(self.session)
                for owner in owners:
                    await dispatcher.notify_lender_rejected(
                        lender_owner_user_id=owner.id,
                        lender_name=lender.commercial_name or lender.legal_name,
                        reason=reason,
                    )
        except Exception:
            pass

        return lender

    async def generate_invitation_code(
        self,
        lender_id: UUID,
        created_by_user_id: UUID,
        expires_in_days: int = 30,
    ) -> LenderInvitation:
        """
        Generate a customer invitation code for this lender.

        Args:
            lender_id: Lender ID
            created_by_user_id: User ID of who created this invitation
            expires_in_days: Days until expiration (default 30)

        Returns:
            Created LenderInvitation with unique code
        """
        # Verify lender exists
        lender = await self.lender_repo.get_or_404(
            lender_id, error_code="LENDER_NOT_FOUND"
        )

        # Generate unique code
        code = secrets.token_urlsafe(32)[:20].upper()

        # Ensure code is unique
        while await self.invitation_repo.get_by_code(code):
            code = secrets.token_urlsafe(32)[:20].upper()

        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        invitation = LenderInvitation(
            lender_id=lender_id,
            code=code,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
            status="active",
        )

        self.session.add(invitation)
        await self.session.flush()

        return invitation

    async def revoke_invitation(self, invitation_id: UUID) -> LenderInvitation:
        """Revoke (deactivate) an invitation code."""
        invitation = await self.invitation_repo.get_or_404(
            invitation_id,
            error_code="INVITATION_NOT_FOUND",
        )

        if invitation.status != "active":
            raise ValidationException("Invitation is not active")

        invitation.status = "revoked"
        await self.session.flush()

        return invitation

    async def mark_invitation_used(
        self,
        invitation_id: UUID,
        customer_id: UUID,
    ) -> LenderInvitation:
        """Mark an invitation as used by a customer."""
        invitation = await self.invitation_repo.get_or_404(
            invitation_id,
            error_code="INVITATION_NOT_FOUND",
        )

        if invitation.used_at:
            raise ValidationException("Invitation has already been used")

        if invitation.status != "active":
            raise ValidationException("Invitation is not active")

        invitation.used_at = datetime.now(timezone.utc)
        invitation.used_by_customer_id = customer_id
        invitation.status = "used"
        await self.session.flush()

        return invitation

    async def add_bank_account(
        self,
        lender_id: UUID,
        bank_name: str,
        account_type: str,
        account_number_masked: str,
        account_holder_name: str,
        is_primary: bool = False,
    ) -> LenderBankAccount:
        """
        Add a bank account to a lender.

        Args:
            lender_id: Lender ID
            bank_name: Bank name (e.g., "Banco de Reservas")
            account_type: "savings" or "checking"
            account_number_masked: Last 4 digits (e.g., "****1234")
            account_holder_name: Account holder name
            is_primary: Mark as primary account

        Returns:
            Created LenderBankAccount
        """
        # Verify lender exists
        await self.lender_repo.get_or_404(lender_id, error_code="LENDER_NOT_FOUND")

        # If marking as primary, unmark current primary
        if is_primary:
            current_primary = await self.bank_account_repo.get_primary_by_lender(
                lender_id
            )
            if current_primary:
                current_primary.is_primary = False

        account = LenderBankAccount(
            lender_id=lender_id,
            bank_name=bank_name,
            account_type=account_type,
            account_number_masked=account_number_masked,
            account_holder_name=account_holder_name,
            is_primary=is_primary,
            currency="DOP",  # Default to Dominican Peso
            status="active",
        )

        self.session.add(account)
        await self.session.flush()

        return account

    async def get_lender_bank_accounts(
        self, lender_id: UUID
    ) -> list[LenderBankAccount]:
        """Get all bank accounts for a lender."""
        await self.lender_repo.get_or_404(lender_id, error_code="LENDER_NOT_FOUND")
        return await self.bank_account_repo.get_by_lender(lender_id)

    async def get_lender_invitations(self, lender_id: UUID) -> list[LenderInvitation]:
        """Get all active invitations for a lender."""
        await self.lender_repo.get_or_404(lender_id, error_code="LENDER_NOT_FOUND")
        return await self.invitation_repo.get_active_by_lender(lender_id)
