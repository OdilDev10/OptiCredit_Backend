"""
OptiCredit Notification System

Scalable notification system based on events.

Structure:
    notifications/
        events.py         - All notification event types
        templates.py      - Message templates for each event
        dispatcher.py     - Routes events to channels
        channels/
            in_app.py     - In-app notifications (DB + SSE)
            email.py      - Email notifications

Usage:
    from app.services.notifications import NotificationDispatcher

    async def some_service_function(session):
        dispatcher = NotificationDispatcher(session)

        # Simple notification
        await dispatcher.dispatch(event)

        # Convenience methods
        await dispatcher.notify_user_disabled(user_id)
        await dispatcher.notify_user_enabled(user_id)
        await dispatcher.notify_lender_approved(owner_user_id, lender_name)
"""

from app.services.notifications.events import NotificationEvent, NotificationEventType
from app.services.notifications.templates import NotificationTemplates
from app.services.notifications.dispatcher import NotificationDispatcher

__all__ = [
    "NotificationDispatcher",
    "NotificationEvent",
    "NotificationEventType",
    "NotificationTemplates",
]
