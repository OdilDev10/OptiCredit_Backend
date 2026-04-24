"""Notification dispatcher - routes notification events to appropriate channels."""

import logging
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.notifications.events import NotificationEvent, NotificationEventType
from app.services.notifications.channels.in_app import InAppChannel
from app.services.notifications.channels.email import EmailChannel
from app.services.notifications.templates import NotificationTemplates

logger = logging.getLogger("app.notifications.dispatcher")

CHANNEL_IN_APP = "in_app"
CHANNEL_EMAIL = "email"


class NotificationDispatcher:
    """
    Notification dispatcher that routes events to configured channels.

    Usage:
        dispatcher = NotificationDispatcher(session)
        await dispatcher.dispatch(event)  # sends to all configured channels
        await dispatcher.dispatch(event, channels=[CHANNEL_IN_APP])  # specific channel
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.in_app = InAppChannel(session)
        self.email = EmailChannel(session)
        self.templates = NotificationTemplates()

    async def dispatch(
        self,
        event: NotificationEvent,
        channels: Sequence[str] | None = None,
    ) -> dict[str, bool]:
        """
        Dispatch a notification event to specified channels.

        Args:
            event: The notification event to dispatch
            channels: List of channels to use. If None, uses all configured.

        Returns:
            Dict mapping channel name to success boolean
        """
        title, message = self.templates.render(event)

        if channels is None:
            channels = [CHANNEL_IN_APP, CHANNEL_EMAIL]

        results = {}

        if CHANNEL_IN_APP in channels:
            try:
                await self.in_app.send(event, title, message)
                results[CHANNEL_IN_APP] = True
            except Exception as e:
                logger.error(f"In-app channel failed: {e}")
                results[CHANNEL_IN_APP] = False

        if CHANNEL_EMAIL in channels:
            try:
                recipient_email = await self.email.get_recipient_email(
                    event.recipient_id
                )
                if recipient_email:
                    await self.email.send(event, title, message, recipient_email)
                    results[CHANNEL_EMAIL] = True
                else:
                    logger.warning(f"No email found for user {event.recipient_id}")
                    results[CHANNEL_EMAIL] = False
            except Exception as e:
                logger.error(f"Email channel failed: {e}")
                results[CHANNEL_EMAIL] = False

        return results

    async def dispatch_to_multiple(
        self,
        events: list[NotificationEvent],
        channels: Sequence[str] | None = None,
    ) -> list[dict[str, bool]]:
        """Dispatch multiple notification events."""
        results = []
        for event in events:
            result = await self.dispatch(event, channels)
            results.append(result)
        return results

    async def notify_user_created(
        self,
        user_id,
        lender_name: str,
        actor_name: str | None = None,
    ) -> dict[str, bool]:
        """Notify user that their account was created."""
        event = NotificationEvent(
            event_type=NotificationEventType.USER_CREATED,
            recipient_id=user_id,
            lender_name=lender_name,
            actor_name=actor_name,
        )
        return await self.dispatch(event)

    async def notify_user_disabled(
        self,
        user_id,
    ) -> dict[str, bool]:
        """Notify user that their account was disabled."""
        event = NotificationEvent(
            event_type=NotificationEventType.USER_DISABLED,
            recipient_id=user_id,
        )
        return await self.dispatch(event)

    async def notify_user_enabled(
        self,
        user_id,
    ) -> dict[str, bool]:
        """Notify user that their account was enabled."""
        event = NotificationEvent(
            event_type=NotificationEventType.USER_ENABLED,
            recipient_id=user_id,
        )
        return await self.dispatch(event)

    async def notify_lender_registered(
        self,
        platform_admin_ids: list,
        lender_name: str,
    ) -> list[dict[str, bool]]:
        """Notify platform admins about a new lender registration."""
        events = [
            NotificationEvent(
                event_type=NotificationEventType.LENDER_REGISTERED,
                recipient_id=admin_id,
                lender_name=lender_name,
            )
            for admin_id in platform_admin_ids
        ]
        return await self.dispatch_to_multiple(events)

    async def notify_lender_approved(
        self,
        lender_owner_user_id,
        lender_name: str,
    ) -> dict[str, bool]:
        """Notify lender owner that their organization was approved."""
        event = NotificationEvent(
            event_type=NotificationEventType.LENDER_APPROVED,
            recipient_id=lender_owner_user_id,
            lender_name=lender_name,
        )
        return await self.dispatch(event)

    async def notify_lender_rejected(
        self,
        lender_owner_user_id,
        lender_name: str,
        reason: str | None = None,
    ) -> dict[str, bool]:
        """Notify lender owner that their organization was rejected."""
        event = NotificationEvent(
            event_type=NotificationEventType.LENDER_REJECTED,
            recipient_id=lender_owner_user_id,
            lender_name=lender_name,
            reason=reason,
        )
        return await self.dispatch(event)

    async def notify_loan_disbursed(
        self,
        customer_user_id,
        amount: float,
        lender_name: str,
    ) -> dict[str, bool]:
        """Notify customer that their loan was disbursed."""
        event = NotificationEvent(
            event_type=NotificationEventType.LOAN_DISBURSED,
            recipient_id=customer_user_id,
            amount=amount,
            lender_name=lender_name,
        )
        return await self.dispatch(event)

    async def notify_installment_overdue(
        self,
        customer_user_id,
        amount: float,
        installment_number: int,
    ) -> dict[str, bool]:
        """Notify customer about an overdue installment."""
        event = NotificationEvent(
            event_type=NotificationEventType.INSTALLMENT_OVERDUE,
            recipient_id=customer_user_id,
            amount=amount,
            installment_number=installment_number,
        )
        return await self.dispatch(event)
