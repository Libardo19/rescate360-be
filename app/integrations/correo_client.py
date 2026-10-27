"""Correo saliente por SMTP.

Con MAIL_ENABLED=false (local, CI y pruebas) no se envía nada: el correo solo queda en el log.
Puerto 465 = TLS directo; cualquier otro (587) = STARTTLS.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TIMEOUT_SEGUNDOS = 30


class ErrorCorreo(Exception):
    """El correo no se pudo enviar (credenciales, red o servidor SMTP)."""


def enviar_correo(para: str, asunto: str, texto: str) -> None:
    settings = get_settings()
    if not settings.mail_enabled:
        logger.info("[correo desactivado] → %s · %s\n%s", para, asunto, texto)
        return
    if not (settings.smtp_host and settings.smtp_user and settings.smtp_password):
        raise ErrorCorreo("Faltan SMTP_HOST / SMTP_USER / SMTP_PASSWORD para enviar correo")

    mensaje = EmailMessage()
    mensaje["From"] = formataddr((settings.mail_from_name, settings.mail_from or settings.smtp_user))
    mensaje["To"] = para
    mensaje["Subject"] = asunto
    mensaje.set_content(texto)

    contexto = ssl.create_default_context()
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SEGUNDOS, context=contexto
            ) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(mensaje)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SEGUNDOS) as smtp:
                smtp.starttls(context=contexto)
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as exc:
        raise ErrorCorreo(str(exc)) from exc
