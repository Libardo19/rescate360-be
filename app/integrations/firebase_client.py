"""Push con Firebase Cloud Messaging (B3).

Sin FIREBASE_CREDENTIALS_PATH (local, CI y pruebas) no se envía nada: el push solo queda en el
log, igual que el SMS sin Twilio. Configurar el proyecto de Firebase y probarlo con teléfonos
reales es la última tarea de Sergio: el JSON va fuera del repo, montado como volumen.
"""

import logging
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# FCM acepta hasta 500 tokens por envío
LOTE_MAXIMO = 500


@lru_cache
def _app():
    # Import aquí: sin credenciales (pruebas, CI) no se carga el SDK
    import firebase_admin
    from firebase_admin import credentials

    return firebase_admin.initialize_app(credentials.Certificate(get_settings().firebase_credentials_path))


def enviar_push(tokens: list[str], titulo: str, cuerpo: str, datos: dict[str, str] | None = None) -> list[str]:
    """Envía el push a esos tokens. Devuelve los tokens que FCM rechazó como inválidos (para borrarlos)."""
    if not tokens:
        return []
    if not get_settings().firebase_credentials_path:
        logger.info("[Push desactivado] → %d dispositivos · %s: %s", len(tokens), titulo, cuerpo)
        return []

    from firebase_admin import messaging

    invalidos: list[str] = []
    for inicio in range(0, len(tokens), LOTE_MAXIMO):
        lote = tokens[inicio : inicio + LOTE_MAXIMO]
        mensaje = messaging.MulticastMessage(
            tokens=lote,
            notification=messaging.Notification(title=titulo, body=cuerpo),
            data=datos or {},
            android=messaging.AndroidConfig(priority="high"),
        )
        respuesta = messaging.send_each_for_multicast(mensaje, app=_app())
        for token, resultado in zip(lote, respuesta.responses, strict=True):
            if not resultado.success and isinstance(resultado.exception, messaging.UnregisteredError):
                invalidos.append(token)
    return invalidos
