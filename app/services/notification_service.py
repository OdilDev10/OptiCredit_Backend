"""Notification service - handles email and in-app notifications."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification_repo import NotificationRepository
from app.services.email_service import email_service
from app.services.sse_manager import sse_manager
from app.config import settings

logger = logging.getLogger("app.notifications")


class NotificationService:
    """Service for creating and sending notifications."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NotificationRepository(session)

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        notification_type: str = "info",
        send_email: bool = False,
    ) -> Notification:
        """Create an in-app notification and optionally send email."""
        notification = await self.repo.create(
            {
                "user_id": user_id,
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "is_read": False,
            }
        )
        await self.session.commit()

        await sse_manager.send_to_user(
            str(user_id),
            "notification",
            {
                "id": str(notification.id),
                "title": title,
                "message": message,
                "type": notification_type,
                "created_at": notification.created_at.isoformat(),
            },
        )

        if send_email:
            user = await self.session.get(User, user_id)
            if user and user.email:
                try:
                    await email_service.send_email(
                        to_email=user.email,
                        subject=title,
                        body=message,
                    )
                except Exception as e:
                    logger.error(f"Failed to send email notification: {e}")

        return notification

    async def notify_application_submitted(
        self,
        lender_user_id: UUID,
        lender_name: str,
        application_id: str,
        amount: Decimal,
        customer_name: str,
    ) -> None:
        """Notify lender about new loan application."""
        title = "Nueva Solicitud de Préstamo"
        message = f"{customer_name} ha solicitado RD$ {amount:,.2f}"

        await self.create_notification(
            user_id=lender_user_id,
            title=title,
            message=message,
            notification_type="application_submitted",
            send_email=True,
        )

    async def notify_application_approved(
        self,
        customer_user_id: UUID,
        customer_name: str,
        application_id: str,
        amount: Decimal,
        lender_name: str,
    ) -> None:
        """Notify customer that their application was approved."""
        title = "¡Solicitud Aprobada!"
        message = f"Tu solicitud a {lender_name} por RD$ {amount:,.2f} ha sido aprobada"

        await self.create_notification(
            user_id=customer_user_id,
            title=title,
            message=message,
            notification_type="application_approved",
            send_email=True,
        )

    async def notify_application_rejected(
        self,
        customer_user_id: UUID,
        customer_name: str,
        application_id: str,
        reason: str | None = None,
        lender_name: str = "",
    ) -> None:
        """Notify customer that their application was rejected."""
        title = "Solicitud No Aprobada"
        message = f"Tu solicitud a {lender_name} no pudo ser aprobada"
        if reason:
            message += f": {reason}"

        await self.create_notification(
            user_id=customer_user_id,
            title=title,
            message=message,
            notification_type="application_rejected",
            send_email=True,
        )

    async def notify_payment_submitted(
        self,
        lender_user_id: UUID,
        payment_id: str,
        amount: Decimal,
        loan_number: str,
        installment_number: int,
        customer_name: str,
    ) -> None:
        """Notify lender about new payment submitted."""
        title = "Nuevo Pago Recibido"
        message = f"{customer_name} realizó pago de RD$ {amount:,.2f} ({loan_number}, cuota #{installment_number})"

        await self.create_notification(
            user_id=lender_user_id,
            title=title,
            message=message,
            notification_type="payment_submitted",
            send_email=True,
        )

    async def notify_payment_approved(
        self,
        customer_user_id: UUID,
        customer_name: str,
        payment_id: str,
        amount: Decimal,
        loan_number: str,
        installment_number: int,
    ) -> None:
        """Notify customer that their payment was approved."""
        title = "¡Pago Aprobado!"
        message = f"Tu pago de RD$ {amount:,.2f} ha sido aprobado ({loan_number}, cuota #{installment_number})"

        await self.create_notification(
            user_id=customer_user_id,
            title=title,
            message=message,
            notification_type="payment_approved",
            send_email=True,
        )

    async def notify_payment_rejected(
        self,
        customer_user_id: UUID,
        customer_name: str,
        payment_id: str,
        amount: Decimal,
        reason: str,
    ) -> None:
        """Notify customer that their payment was rejected."""
        title = "Pago Rechazado"
        message = f"Tu pago de RD$ {amount:,.2f} fue rechazado: {reason}"

        await self.create_notification(
            user_id=customer_user_id,
            title=title,
            message=message,
            notification_type="payment_rejected",
            send_email=True,
        )

    async def notify_password_changed(
        self,
        user_id: UUID,
        ip_address: str | None = None,
    ) -> None:
        """Notify user that their password was changed."""
        title = "Contraseña Cambiada"
        message = "Tu contraseña fue modificada exitosamente"
        if ip_address:
            message += f" desde IP: {ip_address}"

        await self.create_notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type="security",
            send_email=True,
        )

    async def notify_new_login(
        self,
        user_id: UUID,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> None:
        """Notify user about a new login to their account."""
        title = "Nuevo Inicio de Sesión"
        message = "Se detectó un nuevo inicio de sesión en tu cuenta"
        if ip_address:
            message += f" desde IP: {ip_address}"

        await self.create_notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type="security",
            send_email=True,
        )

    async def get_user_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ):
        """Get notifications for a user."""
        return await self.repo.get_user_notifications(
            user_id=user_id,
            unread_only=unread_only,
            skip=skip,
            limit=limit,
        )

    async def mark_as_read(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> Optional[Notification]:
        """Mark a notification as read."""
        return await self.repo.mark_as_read(notification_id, user_id)

    async def mark_all_as_read(self, user_id: UUID) -> int:
        """Mark all notifications as read for user."""
        return await self.repo.mark_all_as_read(user_id)

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications."""
        return await self.repo.get_unread_count(user_id)
