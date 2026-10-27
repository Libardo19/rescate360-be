"""Clasifica un reporte de incidente: prioridad + organización (Gemini, o reglas si no hay IA).

Mismo funcionamiento que clasificar_prioridad_ia: idempotente y sin pisar lo manual.
"""

import logging
from uuid import UUID

from celery import shared_task

from app.core.database import SessionLocal
from app.models.enums import PrioridadSolicitud
from app.repositories import reportes_repository as repo
from app.schemas.ia_schema import CasoIA
from app.services import ia_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30, retry_backoff=True)
def clasificar_reporte_ia(self, reporte_id: str) -> dict:
    db = SessionLocal()
    try:
        reporte = repo.obtener_para_clasificar(db, UUID(reporte_id))
        if reporte is None:
            logger.warning("clasificar_reporte_ia: reporte %s no encontrado", reporte_id)
            return {"status": "no_encontrado", "reporte_id": reporte_id}
        if reporte.prioridad_ia != PrioridadSolicitud.PENDIENTE:
            return {"status": "ya_clasificado", "reporte_id": reporte_id}

        caso = CasoIA(
            clase="reporte",
            tipo=reporte.tipo,
            descripcion=reporte.descripcion,
            direccion=reporte.direccion,
            evidencias=len(reporte.evidencias),
        )
        resultado = ia_service.clasificar(caso, ia_service.organizaciones_activas(db))
        repo.aplicar_clasificacion_ia(
            db,
            reporte,
            prioridad_ia=resultado.prioridad,
            organizacion_objetivo_id=resultado.organizacion_id,
            confianza_ia=resultado.confianza,
            razonamiento_ia=resultado.razonamiento,
        )
        db.commit()
        logger.info(
            "Reporte %s clasificado (%s): %s / org %s",
            reporte_id, resultado.fuente, resultado.prioridad.value, resultado.organizacion_id,
        )
        return {
            "status": "ok",
            "reporte_id": reporte_id,
            "fuente": resultado.fuente,
            "prioridad_ia": resultado.prioridad.value,
            "organizacion_objetivo_id": str(resultado.organizacion_id) if resultado.organizacion_id else None,
        }
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
