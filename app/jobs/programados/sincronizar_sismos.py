"""Cada minuto: registra los sismos nuevos de todo el mundo y atiende los fuertes de Colombia (B8).

- Se guardan todos (el mapa los muestra); solo los de Colombia publican alerta y "¿Estás bien?".
- Cada minuto se lee el feed de la última hora; cada 30 min (`dia=True`) el del día completo,
  para recuperar lo que se perdió si el worker estuvo apagado.
- Idempotente: un sismo se registra una sola vez (por id_externo) y su alerta se publica una sola
  vez (alerta_id). Los que ya existen se descartan con una sola consulta, sin tocarlos uno a uno.
"""

import logging

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.integrations import sismos_client
from app.repositories import sismos_repository
from app.services import sismos_service

logger = logging.getLogger(__name__)


@celery_app.task
def sincronizar_sismos(dia: bool = False) -> dict:
    db = SessionLocal()
    try:
        feed = sismos_client.obtener_recientes(get_settings().sismos_feed_dia_url if dia else None)
        existentes = sismos_repository.ids_externos_existentes(db, [s.id_externo for s in feed])
        nuevos = atendidos = 0
        for sismo in feed:
            if sismo.id_externo in existentes:
                continue
            evento, es_nuevo = sismos_service.registrar(db, sismo)
            nuevos += es_nuevo
            if sismos_service.atender_si_es_fuerte(db, evento):
                atendidos += 1
                logger.info("Sismo %s M%.1f atendido: alerta %s", evento.id_externo, evento.magnitud, evento.alerta_id)
        return {"status": "ok", "nuevos": nuevos, "alertados": atendidos}
    finally:
        db.close()
