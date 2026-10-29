"""Cada minuto: registra los sismos nuevos de Colombia y atiende los fuertes (B8).

Idempotente: un sismo se registra una sola vez (por id_externo) y su alerta se publica una sola
vez (alerta_id). Si el feed no responde, no pasa nada: se vuelve a intentar al minuto siguiente.
"""

import logging

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.integrations import sismos_client
from app.services import sismos_service

logger = logging.getLogger(__name__)


@celery_app.task
def sincronizar_sismos() -> dict:
    db = SessionLocal()
    try:
        nuevos = atendidos = 0
        for sismo in sismos_client.obtener_recientes():
            evento, es_nuevo = sismos_service.registrar(db, sismo)
            nuevos += es_nuevo
            if sismos_service.atender_si_es_fuerte(db, evento):
                atendidos += 1
                logger.info("Sismo %s M%.1f atendido: alerta %s", evento.id_externo, evento.magnitud, evento.alerta_id)
        return {"status": "ok", "nuevos": nuevos, "alertados": atendidos}
    finally:
        db.close()
