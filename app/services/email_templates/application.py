"""Application notification email templates."""

from app.services.email_templates.base import render_template


def get_application_submitted_email_html(
    recipient_name: str,
    application_id: str,
    lender_name: str,
    amount: str,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for application submitted notification to lender."""
    content = f"""
    <h2>Nueva Solicitud de Préstamo</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Se ha recibido una nueva solicitud de préstamo en <strong>{lender_name}</strong>.</p>
    
    <div class="info-box">
        <p><strong>ID de Solicitud:</strong> {application_id}</p>
        <p><strong>Monto Solicitado:</strong> {amount}</p>
    </div>
    
    <p>Puedes revisar y procesar esta solicitud en tu panel de gestión.</p>
    
    <p style="text-align: center;">
        <a href="#" class="button">Ver Solicitud</a>
    </p>
    """
    return render_template(
        title=f"Nueva Solicitud - {app_name}", content=content, app_name=app_name
    )


def get_application_approved_email_html(
    recipient_name: str,
    application_id: str,
    lender_name: str,
    amount: str,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for application approved notification to customer."""
    content = f"""
    <h2>¡Felicitaciones! Tu Solicitud fue Aprobada</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Great news! <strong>{lender_name}</strong> ha aprobado tu solicitud de préstamo.</p>
    
    <div class="info-box" style="background-color: #d1fae5; border-left-color: #10b981;">
        <p><strong>ID de Solicitud:</strong> {application_id}</p>
        <p><strong>Monto Aprobado:</strong> {amount}</p>
    </div>
    
    <p>Nos pondremos en contacto contigo para el desembolso.</p>
    
    <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
    """
    return render_template(
        title=f"Solicitud Aprobada - {app_name}", content=content, app_name=app_name
    )


def get_application_rejected_email_html(
    recipient_name: str,
    application_id: str,
    lender_name: str,
    reason: str | None = None,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for application rejected notification to customer."""
    content = f"""
    <h2>Estado de tu Solicitud</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Lamentamos informarte que <strong>{lender_name}</strong> no pudo aprobar tu solicitud de préstamo en esta ocasión.</p>
    
    <div class="warning-box">
        <p><strong>ID de Solicitud:</strong> {application_id}</p>
        {f"<p><strong>Motivo:</strong> {reason}</p>" if reason else ""}
    </div>
    
    <p>Te animamos a volver a aplicar en el futuro cuando tu situación financiera lo permita.</p>
    
    <p>Si tienes alguna pregunta, no dudes en contactarnos.</p>
    """
    return render_template(
        title=f"Solicitud No Aprobada - {app_name}", content=content, app_name=app_name
    )
