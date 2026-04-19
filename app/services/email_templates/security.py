"""Security notification email templates."""

from app.services.email_templates.base import render_template


def get_password_changed_email_html(
    recipient_name: str,
    changed_at: str,
    ip_address: str | None = None,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for password changed notification."""
    content = f"""
    <h2>Contraseña Cambiada</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Tu contraseña fue cambiada exitosamente.</p>
    
    <div class="info-box">
        <p><strong>Fecha:</strong> {changed_at}</p>
        {f"<p><strong>Dirección IP:</strong> {ip_address}</p>" if ip_address else ""}
    </div>
    
    <div class="warning-box">
        <strong>⚠️ Si no fuiste tú:</strong> Contacta a nuestro equipo de soporte inmediatamente y considera cambiar tu contraseña nuevamente.
    </div>
    """
    return render_template(
        title=f"Contraseña Cambiada - {app_name}", content=content, app_name=app_name
    )


def get_new_login_email_html(
    recipient_name: str,
    login_time: str,
    ip_address: str | None = None,
    device_info: str | None = None,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for new login notification."""
    content = f"""
    <h2>Nuevo Inicio de Sesión</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Se detectó un nuevo inicio de sesión en tu cuenta.</p>
    
    <div class="info-box">
        <p><strong>Fecha y Hora:</strong> {login_time}</p>
        {f"<p><strong>Dirección IP:</strong> {ip_address}</p>" if ip_address else ""}
        {f"<p><strong>Dispositivo:</strong> {device_info}</p>" if device_info else ""}
    </div>
    
    <div class="warning-box">
        <strong>⚠️ Si no fuiste tú:</strong> proteja su cuenta cambiando su contraseña inmediatamente.
    </div>
    """
    return render_template(
        title=f"Nuevo Inicio de Sesión - {app_name}", content=content, app_name=app_name
    )


def get_security_alert_email_html(
    recipient_name: str,
    alert_type: str,
    description: str,
    action_taken: str | None = None,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for security alert."""
    content = f"""
    <h2>⚠️ Alerta de Seguridad</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>{description}</p>
    
    <div class="warning-box">
        <p><strong>Tipo de Alerta:</strong> {alert_type}</p>
        {f"<p><strong>Acción Tomada:</strong> {action_taken}</p>" if action_taken else ""}
    </div>
    
    <p>Si tienes alguna pregunta o crees que hay un problema con tu cuenta, contacta a nuestro equipo de soporte.</p>
    
    <p style="text-align: center;">
        <a href="#" class="button button-secondary">Contactar Soporte</a>
    </p>
    """
    return render_template(
        title=f"Alerta de Seguridad - {app_name}", content=content, app_name=app_name
    )
