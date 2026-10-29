"""Push a los usuarios que están dentro del círculo de una alerta (B3).

Solo cuenta la ubicación reciente (menos de 24 h): una ubicación vieja no dice dónde está la
persona ahora. Sin credenciales de Firebase el push queda en el log.
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
def notificar_alerta_zona(alerta_id: str) -> dict:
    db = SessionLocal()
    try:
        alerta = db.get(Alerta, UUID(alerta_id))
        if alerta is None or alerta.estado != EstadoAlerta.ACTIVA:
            return {"status": "no_aplica", "alerta_id": alerta_id}
        usuarios = alertas_repository.usuarios_en_la_zona(db, alerta, HORAS_UBICACION)
        dispositivos = notificaciones_service.notificar_usuarios(
            db,
            usuarios,
            titulo=f"Alerta {alerta.nivel.value}: {alerta.titulo}",
            cuerpo=alerta.mensaje,
            datos={"tipo": "alerta", "alerta_id": alerta_id},
        )
        logger.info("Alerta %s: %d usuarios en la zona, %d dispositivos", alerta_id, len(usuarios), dispositivos)
        return {"status": "ok", "alerta_id": alerta_id, "usuarios": len(usuarios), "dispositivos": dispositivos}
    finally:
        db.close()
