"""SMS con Twilio: códigos de recuperación y, en B3, el respaldo del SOS.

Sin TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER (local, CI y pruebas) no se
envía nada: el SMS solo queda en el log. Con la cuenta de prueba de Twilio solo llegan SMS a
números verificados en la consola, y hay que habilitar Colombia en Geo permissions.
"""

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ErrorSMS(Exception):
    """Twilio rechazó el SMS o no hubo red."""


def enviar_sms(telefono: str, mensaje: str) -> None:
    """`telefono` en E.164 (+573001234567), como se guarda en la BD."""
    settings = get_settings()
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number):
        logger.info("[SMS desactivado] → %s · %s", telefono, mensaje)
        return

    # Import aquí: sin credenciales (pruebas, CI) no se carga el SDK
    from twilio.base.exceptions import TwilioException
    from twilio.rest import Client

    try:
        Client(settings.twilio_account_sid, settings.twilio_auth_token).messages.create(
            to=telefono, from_=settings.twilio_from_number, body=mensaje
        )
    except TwilioException as exc:
        raise ErrorSMS(str(exc)) from exc
