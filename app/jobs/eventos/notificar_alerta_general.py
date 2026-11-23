"""Push a TODOS los usuarios activos por un sismo muy fuerte (B8), según dónde está cada uno.

Se usa en lugar de `notificar_alerta_zona` cuando la magnitud llega a
SISMOS_MAGNITUD_ALERTA_GENERAL:

- Quien tiene su ubicación reciente (menos de 24 h) DENTRO del radio de afectación recibe la
  alerta SOS: `urgente=1`, la app la muestra en pantalla completa con el botón de SOS (además
  del "¿Estás bien?" que abre el job de sismos).
- Todos los demás (lejos del epicentro o sin ubicación reciente) reciben solo un aviso
  informativo de que hubo un sismo y dónde: `urgente=0`, sin SOS.

Sin credenciales de Firebase el push queda en el log.
"""

import logging
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.alerta import Alerta
from app.models.enums import EstadoAlerta
from app.repositories import alertas_repository
from app.services import notificaciones_service

logger = logging.getLogger(__name__)

HORAS_UBICACION = 24


@celery_app.task
def notificar_alerta_general(alerta_id: str) -> dict:
    db = SessionLocal()
    try:
        alerta = db.get(Alerta, UUID(alerta_id))
        if alerta is None or alerta.estado != EstadoAlerta.ACTIVA:
            return {"status": "no_aplica", "alerta_id": alerta_id}
        en_zona = set(alertas_repository.usuarios_en_la_zona(db, alerta, HORAS_UBICACION))
        lejos = [u for u in alertas_repository.usuarios_activos(db) if u not in en_zona]

        dispositivos = notificaciones_service.notificar_usuarios(
            db,
            en_zona,
            titulo=f"🚨 {alerta.titulo}",
            cuerpo=alerta.mensaje,
            datos={"tipo": "alerta", "alerta_id": alerta_id, "urgente": "1"},
        )
        dispositivos += notificaciones_service.notificar_usuarios(
            db,
            lejos,
            titulo=alerta.titulo,
            cuerpo=f"{alerta.mensaje.split('. ', 1)[0]}. Estás lejos del epicentro: mantente informado.",
            datos={"tipo": "alerta", "alerta_id": alerta_id, "urgente": "0"},
        )
        logger.info(
            "Alerta general %s: %d en la zona (SOS), %d informados, %d dispositivos",
            alerta_id,
            len(en_zona),
            len(lejos),
            dispositivos,
        )
        return {
            "status": "ok",
            "alerta_id": alerta_id,
            "en_zona": len(en_zona),
            "informados": len(lejos),
            "dispositivos": dispositivos,
        }
    finally:
        db.close()
