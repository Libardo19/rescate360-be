"""Cada minuto: los "¿Estás bien?" sin responder a tiempo quedan sin_respuesta, se sube un SOS
automático con la última ubicación conocida (si se conoce) y se avisa por SMS a los contactos.
"""

import logging

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.integrations.twilio_client import ErrorSMS, enviar_sms
from app.repositories import contactos_emergencia_repository
from app.services import check_ins_service
from app.utils.geo import latlng_desde_punto

logger = logging.getLogger(__name__)


def mensaje_sin_respuesta(nombre: str, posicion: dict | None) -> str:
    donde = (
        f"Pedimos ayuda a los organismos de rescate. Última ubicación: "
        f"https://maps.google.com/?q={posicion['lat']:.5f},{posicion['lng']:.5f} "
        if posicion
        else "No tenemos su ubicación. "
    )
    return f"RESCATE360: {nombre} no respondió si está bien tras una emergencia. {donde}Si no logras comunicarte, llama al 123."


@celery_app.task
def vencer_check_ins() -> dict:
    db = SessionLocal()
    try:
        vencidos = check_ins_service.vencer(db)
        avisados = 0
        for check_in, usuario in vencidos:
            texto = mensaje_sin_respuesta(usuario.nombre, latlng_desde_punto(check_in.ultima_ubicacion))
            for contacto in contactos_emergencia_repository.listar_de_usuario(db, usuario.id):
                try:
                    enviar_sms(contacto.telefono, texto)
                    avisados += 1
                except ErrorSMS:
                    logger.exception("Check-in %s: no se pudo avisar al contacto %s", check_in.id, contacto.id)
        return {"status": "ok", "vencidos": len(vencidos), "sms": avisados}
    finally:
        db.close()
