"""Cada día: borra los datos personales que ya pasaron su tiempo de retención (Ley 1581, B6).

- Ubicación actual de los usuarios guardada hace más de RETENCION_UBICACIONES_DIAS (30).
- Mensajes sin conexión ya procesados de hace más de esos mismos días (traen una ubicación).
- Sismos de fuera de Colombia de hace más de RETENCION_SISMOS_MUNDO_DIAS (7): solo sirven para
  el mapa, que muestra las últimas 24 h. Los de Colombia se guardan como historial.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.cola_alerta_offline import ColaAlertaOffline
from app.models.usuario import Usuario
from app.repositories import sismos_repository

RETENCION_SISMOS_MUNDO_DIAS = 7

logger = logging.getLogger(__name__)


@celery_app.task
def limpiar_datos_retencion() -> dict:
    db = SessionLocal()
    try:
        limite = datetime.now(UTC) - timedelta(days=get_settings().retencion_ubicaciones_dias)
        ubicaciones = db.execute(
            update(Usuario)
            .where(Usuario.ubicacion_actual.is_not(None), Usuario.ubicacion_actualizada_en < limite)
            .values(ubicacion_actual=None, ubicacion_actualizada_en=None)
        ).rowcount
        mensajes = db.execute(
            delete(ColaAlertaOffline).where(
                ColaAlertaOffline.sincronizado.is_(True), ColaAlertaOffline.recibido_en < limite
            )
        ).rowcount
        sismos = sismos_repository.borrar_lejanos_viejos(
            db, antes_de=datetime.now(UTC) - timedelta(days=RETENCION_SISMOS_MUNDO_DIAS)
        )
        db.commit()
        logger.info(
            "Retención: %d ubicaciones, %d mensajes sin conexión y %d sismos lejanos borrados",
            ubicaciones,
            mensajes,
            sismos,
        )
        return {"status": "ok", "ubicaciones": ubicaciones, "mensajes_offline": mensajes, "sismos_mundo": sismos}
    finally:
        db.close()
