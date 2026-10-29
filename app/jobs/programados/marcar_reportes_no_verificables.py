"""Cada hora: los reportes que siguen pendientes después de 72 horas pasan a no_verificable (B6).

Nadie los pudo confirmar a tiempo: dejan de salir en el mapa y se cancelan sus asignaciones.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.enums import EstadoReporte
from app.models.reporte import Reporte
from app.repositories import asignaciones_repository

logger = logging.getLogger(__name__)

HORAS_PARA_VERIFICAR = 72


@celery_app.task
def marcar_reportes_no_verificables() -> dict:
    db = SessionLocal()
    try:
        limite = datetime.now(UTC) - timedelta(hours=HORAS_PARA_VERIFICAR)
        vencidos = db.scalars(
            select(Reporte)
            .where(Reporte.estado == EstadoReporte.PENDIENTE, Reporte.creado_en < limite)
            .with_for_update(skip_locked=True)
        ).all()
        for reporte in vencidos:
            asignaciones_repository.cancelar_activas_de_reporte(db, reporte.id)
            reporte.estado = EstadoReporte.NO_VERIFICABLE
        db.commit()
        if vencidos:
            logger.info("Reportes no verificables: %d", len(vencidos))
        return {"status": "ok", "marcados": len(vencidos)}
    finally:
        db.close()
