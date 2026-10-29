"""SMS a los contactos de emergencia cuando alguien activa el SOS (A6).

Llega aunque el contacto no tenga la app ni internet: es el respaldo del SOS. Sin credenciales
de Twilio el SMS solo queda en el log (ver twilio_client).

Sin reintentos a propósito: si un contacto falla se registra y se sigue con los demás; reintentar
el job completo les repetiría el SMS a los que sí lo recibieron.
"""

import logging
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.integrations.twilio_client import ErrorSMS, enviar_sms
from app.models.enums import OrigenSolicitud
from app.models.solicitud_ayuda import SolicitudAyuda
from app.repositories import contactos_emergencia_repository, usuarios_repository
from app.utils.geo import latlng_desde_punto

logger = logging.getLogger(__name__)


def mensaje_sos(nombre: str, lat: float, lng: float) -> str:
    return (
        f"RESCATE360: {nombre} activó un SOS. Ubicación: https://maps.google.com/?q={lat:.5f},{lng:.5f} "
        "Si no logras comunicarte, llama al 123."
    )


@celery_app.task
def enviar_sms_respaldo(solicitud_id: str) -> dict:
    db = SessionLocal()
    try:
        solicitud = db.get(SolicitudAyuda, UUID(solicitud_id))
        if solicitud is None or solicitud.origen != OrigenSolicitud.SOS:
            return {"status": "no_aplica", "solicitud_id": solicitud_id}
        usuario = usuarios_repository.obtener_por_id(db, solicitud.usuario_id)
        contactos = contactos_emergencia_repository.listar_de_usuario(db, solicitud.usuario_id)
        if usuario is None or not contactos:
            return {"status": "sin_contactos", "solicitud_id": solicitud_id}

        ubicacion = latlng_desde_punto(solicitud.ubicacion)
        texto = mensaje_sos(usuario.nombre, ubicacion["lat"], ubicacion["lng"])
        enviados = 0
        for contacto in contactos:
            try:
                enviar_sms(contacto.telefono, texto)
                enviados += 1
            except ErrorSMS:
                logger.exception("SOS %s: no se pudo enviar el SMS al contacto %s", solicitud_id, contacto.id)
        return {"status": "ok", "solicitud_id": solicitud_id, "enviados": enviados, "contactos": len(contactos)}
    finally:
        db.close()
