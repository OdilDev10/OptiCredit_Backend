"""In-app notification channel - stores notifications in DB and sends via SSE."""

import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.repositories.notification_repo import NotificationRepository
from app.services.sse_manager import sse_manager

if TYPE_CHECKING:
    from app.services.notifications.events import NotificationEvent

logger = logging.getLogger("app.notifications.channel.in_app")


class InAppChannel:
    """Sends notifications as in-app notifications (DB + SSE)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NotificationRepository(session)

    async def send(
        self,
        event: "NotificationEvent",
        title: str,
        message: str,
    ) -> Notification | None:
        """Send in-app notification."""
        try:
            notification = await self.repo.create(
                {
                    "user_id": event.recipient_id,
                    "title": title,
                    "message": message,
                    "notification_type": event.event_type.value,
                    "is_read": False,
                }
            )
            await self.session.commit()

            await sse_manager.send_to_user(
                str(event.recipient_id),
                "notification",
                {
                    "id": str(notification.id),
                    "title": title,
                    "message": message,
                    "type": event.event_type.value,
                    "created_at": notification.created_at.isoformat(),
                },
            )

            logger.debug(
                f"In-app notification sent to user {event.recipient_id}: {title}"
            )
            return notification

        except Exception as e:
            logger.error(f"Failed to send in-app notification: {e}")
            return None
