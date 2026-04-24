"""Email notification channel - sends notifications via email."""

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.email_service import email_service

if TYPE_CHECKING:
    from app.services.notifications.events import NotificationEvent

logger = logging.getLogger("app.notifications.channel.email")


class EmailChannel:
    """Sends notifications via email."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def send(
        self,
        event: "NotificationEvent",
        title: str,
        message: str,
        recipient_email: str,
    ) -> bool:
        """Send email notification."""
        try:
            await email_service.send_email(
                to_email=recipient_email,
                subject=title,
                body=message,
            )
            logger.debug(f"Email notification sent to {recipient_email}: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            return False

    async def get_recipient_email(self, user_id) -> str | None:
        """Get email for a user."""
        user = await self.session.get(User, user_id)
        return user.email if user else None
