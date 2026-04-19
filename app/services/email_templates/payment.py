"""Payment notification email templates."""

from app.services.email_templates.base import render_template


def get_payment_approved_email_html(
    recipient_name: str,
    payment_id: str,
    amount: str,
    installment_number: int,
    loan_number: str,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for payment approved notification to customer."""
    content = f"""
    <h2>¡Pago Aprobado!</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Tu pago ha sido verificado y aprobado exitosamente.</p>
    
    <div class="info-box" style="background-color: #d1fae5; border-left-color: #10b981;">
        <p><strong>ID de Pago:</strong> {payment_id}</p>
        <p><strong>Monto:</strong> {amount}</p>
        <p><strong>Préstamo:</strong> {loan_number}</p>
        <p><strong>Cuota #:</strong> {installment_number}</p>
    </div>
    
    <p>Gracias por tu pago. Este ha sido aplicado a tu cuenta.</p>
    """
    return render_template(
        title=f"Pago Aprobado - {app_name}", content=content, app_name=app_name
    )


def get_payment_rejected_email_html(
    recipient_name: str,
    payment_id: str,
    amount: str,
    reason: str,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for payment rejected notification to customer."""
    content = f"""
    <h2>Pago Rechazado</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Tu pago no pudo ser procesado. Por favor revisa la información e intenta nuevamente.</p>
    
    <div class="warning-box">
        <p><strong>ID de Pago:</strong> {payment_id}</p>
        <p><strong>Monto:</strong> {amount}</p>
        <p><strong>Motivo:</strong> {reason}</p>
    </div>
    
    <p>Si crees que hay un error, contacta a nuestro equipo de soporte.</p>
    
    <p style="text-align: center;">
        <a href="#" class="button">Contactar Soporte</a>
    </p>
    """
    return render_template(
        title=f"Pago Rechazado - {app_name}", content=content, app_name=app_name
    )


def get_payment_pending_review_email_html(
    recipient_name: str,
    payment_id: str,
    amount: str,
    voucher_id: str,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for payment pending review notification to lender."""
    content = f"""
    <h2>Pago Pendiente de Revisión</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Se ha recibido un nuevo pago que requiere tu revisión.</p>
    
    <div class="info-box">
        <p><strong>ID de Pago:</strong> {payment_id}</p>
        <p><strong>Monto:</strong> {amount}</p>
        <p><strong>ID de Comprobante:</strong> {voucher_id}</p>
    </div>
    
    <p>Por favor revisa el comprobante y approves o rechaza el pago.</p>
    
    <p style="text-align: center;">
        <a href="#" class="button">Revisar Pago</a>
    </p>
    """
    return render_template(
        title=f"Pago Pendiente - {app_name}", content=content, app_name=app_name
    )


def get_payment_received_email_html(
    recipient_name: str,
    payment_id: str,
    amount: str,
    loan_number: str,
    installment_number: int,
    app_name: str = "OptiCredit",
) -> str:
    """Generate HTML for payment received notification to lender."""
    content = f"""
    <h2>Pago Recibido</h2>
    
    <p>Hola, <strong>{recipient_name}</strong>.</p>
    
    <p>Se ha registrado un nuevo pago en tu cartera.</p>
    
    <div class="info-box" style="background-color: #d1fae5; border-left-color: #10b981;">
        <p><strong>ID de Pago:</strong> {payment_id}</p>
        <p><strong>Monto:</strong> {amount}</p>
        <p><strong>Préstamo:</strong> {loan_number}</p>
        <p><strong>Cuota #:</strong> {installment_number}</p>
    </div>
    
    <p>El pago está siendo procesado. Recibirás una notificación cuando sea aprobado.</p>
    """
    return render_template(
        title=f"Pago Recibido - {app_name}", content=content, app_name=app_name
    )
