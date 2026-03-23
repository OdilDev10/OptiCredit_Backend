"""Email service for sending emails."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings


class EmailService:
    """Service for sending emails."""

    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = settings.smtp_email
        self.sender_password = settings.smtp_password

    async def send_verification_email(self, to_email: str, token: str, app_name: str = "Kashap") -> bool:
        """Send email verification link to user."""
        verification_link = f"{settings.app_url}/verify-email?token={token}"

        subject = "Verifica tu correo electrónico"
        html_template = """
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Bienvenido a {app_name}</h2>
                <p>Gracias por registrarte. Por favor, verifica tu correo electrónico haciendo clic en el botón de abajo:</p>
                <p><a href="{link}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verificar Email</a></p>
                <p>O copia este enlace en tu navegador:</p>
                <p>{link}</p>
                <p>Este enlace expira en 24 horas.</p>
                <p>Si no solicitaste este email, ignóralo.</p>
            </body>
        </html>
        """

        return await self._send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_template.format(app_name=app_name, link=verification_link)
        )

    async def send_password_reset_email(self, to_email: str, token: str, app_name: str = "Kashap") -> bool:
        """Send password reset link to user."""
        reset_link = f"{settings.app_url}/reset-password?token={token}"

        subject = "Recupera tu contraseña"
        html_template = """
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Recuperación de Contraseña</h2>
                <p>Recibimos una solicitud para recuperar tu contraseña. Haz clic en el botón de abajo para crear una nueva:</p>
                <p><a href="{link}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Recuperar Contraseña</a></p>
                <p>O copia este enlace en tu navegador:</p>
                <p>{link}</p>
                <p>Este enlace expira en 1 hora.</p>
                <p>Si no solicitaste esto, ignora este email y tu contraseña permanecerá sin cambios.</p>
            </body>
        </html>
        """

        return await self._send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_template.format(link=reset_link)
        )

    async def send_otp_email(self, to_email: str, otp_code: str) -> bool:
        """Send OTP code to user."""
        subject = "Tu código de verificación"
        html_template = """
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Código de Verificación</h2>
                <p>Tu código de verificación es:</p>
                <h1 style="background-color: #f0f0f0; padding: 20px; text-align: center; letter-spacing: 5px;">{otp_code}</h1>
                <p>Este código expira en 10 minutos.</p>
                <p>Si no solicitaste este código, ignora este email.</p>
            </body>
        </html>
        """

        return await self._send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_template.format(otp_code=otp_code)
        )

    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send generic email with plain text body."""
        # Convert plain text to HTML
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <pre>{body}</pre>
            </body>
        </html>
        """
        return await self._send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content
        )

    async def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Internal method to send email."""
        try:
            # For development, just log
            if settings.environment == "development":
                print(f"[EMAIL] To: {to_email}")
                print(f"[EMAIL] Subject: {subject}")
                print(f"[EMAIL] Content: {html_content}\n")
                return True

            # For production, use SMTP
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = to_email

            part = MIMEText(html_content, "html")
            message.attach(part)

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, to_email, message.as_string())

            return True
        except Exception as e:
            print(f"[ERROR] Failed to send email to {to_email}: {str(e)}")
            return False


# Singleton instance
email_service = EmailService()
