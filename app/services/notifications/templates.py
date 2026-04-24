"""Notification templates - generates title and message for each event type."""

from app.services.notifications.events import NotificationEvent, NotificationEventType


class NotificationTemplates:
    """Generates title and message for notification events."""

    @staticmethod
    def render(event: NotificationEvent) -> tuple[str, str]:
        """Render title and message for a notification event."""
        method = f"_render_{event.event_type.value}"
        if hasattr(NotificationTemplates, method):
            return getattr(NotificationTemplates, method)(event)
        return NotificationTemplates._render_default(event)

    @staticmethod
    def _render_default(event: NotificationEvent) -> tuple[str, str]:
        """Default renderer."""
        title = "Notificación"
        message = f"Evento: {event.event_type.value}"
        return title, message

    @staticmethod
    def _render_application_submitted(event: NotificationEvent) -> tuple[str, str]:
        amount_str = f"RD$ {event.amount:,.2f}" if event.amount else "N/A"
        title = "Nueva Solicitud de Préstamo"
        message = f"{event.actor_name} ha solicitado {amount_str}"
        return title, message

    @staticmethod
    def _render_application_approved(event: NotificationEvent) -> tuple[str, str]:
        amount_str = f"RD$ {event.amount:,.2f}" if event.amount else "N/A"
        title = "¡Solicitud Aprobada!"
        message = (
            f"Tu solicitud a {event.lender_name} por {amount_str} ha sido aprobada"
        )
        return title, message

    @staticmethod
    def _render_application_rejected(event: NotificationEvent) -> tuple[str, str]:
        title = "Solicitud No Aprobada"
        message = f"Tu solicitud a {event.lender_name} no pudo ser aprobada"
        if event.reason:
            message += f": {event.reason}"
        return title, message

    @staticmethod
    def _render_payment_submitted(event: NotificationEvent) -> tuple[str, str]:
        amount_str = f"RD$ {event.amount:,.2f}" if event.amount else "N/A"
        title = "Nuevo Pago Recibido"
        installment = (
            f", cuota #{event.installment_number}" if event.installment_number else ""
        )
        message = f"{event.actor_name} realizó pago de {amount_str} ({event.loan_number}{installment})"
        return title, message

    @staticmethod
    def _render_payment_approved(event: NotificationEvent) -> tuple[str, str]:
        amount_str = f"RD$ {event.amount:,.2f}" if event.amount else "N/A"
        title = "¡Pago Aprobado!"
        installment = (
            f", cuota #{event.installment_number}" if event.installment_number else ""
        )
        message = f"Tu pago de {amount_str} ha sido aprobado ({event.loan_number}{installment})"
        return title, message

    @staticmethod
    def _render_payment_rejected(event: NotificationEvent) -> tuple[str, str]:
        amount_str = f"RD$ {event.amount:,.2f}" if event.amount else "N/A"
        title = "Pago Rechazado"
        message = f"Tu pago de {amount_str} fue rechazado"
        if event.reason:
            message += f": {event.reason}"
        return title, message

    @staticmethod
    def _render_user_created(event: NotificationEvent) -> tuple[str, str]:
        title = "Cuenta Creada"
        message = f"Se ha creado tu cuenta en {event.lender_name}"
        if event.actor_name:
            message += f" por {event.actor_name}"
        return title, message

    @staticmethod
    def _render_user_disabled(event: NotificationEvent) -> tuple[str, str]:
        title = "Cuenta Deshabilitada"
        message = "Tu cuenta ha sido deshabilitada. Contacta a tu administrador para más información."
        return title, message

    @staticmethod
    def _render_user_enabled(event: NotificationEvent) -> tuple[str, str]:
        title = "Cuenta Habilitada"
        message = "Tu cuenta ha sido habilitada nuevamente. Ya puedes iniciar sesión."
        return title, message

    @staticmethod
    def _render_user_role_changed(event: NotificationEvent) -> tuple[str, str]:
        title = "Rol Actualizado"
        message = "Tu rol en la plataforma ha sido actualizado."
        return title, message

    @staticmethod
    def _render_lender_registered(event: NotificationEvent) -> tuple[str, str]:
        title = "Nuevo Lender Registrado"
        message = f"{event.lender_name} se ha registrado y está pendiente de aprobación"
        return title, message

    @staticmethod
    def _render_lender_approved(event: NotificationEvent) -> tuple[str, str]:
        title = "¡Lender Aprobado!"
        message = f"Tu organización {event.lender_name} ha sido aprobada. Ya puedes operar en la plataforma."
        return title, message

    @staticmethod
    def _render_lender_rejected(event: NotificationEvent) -> tuple[str, str]:
        title = "Lender No Aprobado"
        message = f"Tu organización {event.lender_name} no pudo ser aprobada"
        if event.reason:
            message += f": {event.reason}"
        return title, message

    @staticmethod
    def _render_loan_disbursed(event: NotificationEvent) -> tuple[str, str]:
        amount_str = f"RD$ {event.amount:,.2f}" if event.amount else "N/A"
        title = "¡Préstamo Desembolsado!"
        message = f"Tu préstamo de {amount_str} ha sido desembolsado. Revisa tu cuenta."
        return title, message

    @staticmethod
    def _render_installment_overdue(event: NotificationEvent) -> tuple[str, str]:
        amount_str = f"RD$ {event.amount:,.2f}" if event.amount else "N/A"
        title = "Cuota Vencida"
        installment = (
            f"cuota #{event.installment_number}"
            if event.installment_number
            else "una cuota"
        )
        message = f"Tienes {installment} vencida por {amount_str}. Realiza tu pago pronto para evitar intereses."
        return title, message

    @staticmethod
    def _render_password_changed(event: NotificationEvent) -> tuple[str, str]:
        title = "Contraseña Cambiada"
        message = "Tu contraseña fue modificada exitosamente"
        if event.ip_address:
            message += f" desde IP: {event.ip_address}"
        return title, message

    @staticmethod
    def _render_new_login(event: NotificationEvent) -> tuple[str, str]:
        title = "Nuevo Inicio de Sesión"
        message = "Se detectó un nuevo inicio de sesión en tu cuenta"
        if event.ip_address:
            message += f" desde IP: {event.ip_address}"
        return title, message
