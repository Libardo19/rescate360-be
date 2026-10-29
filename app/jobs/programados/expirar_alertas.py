"""Cada 5 minutos: las alertas activas cuyo `expira_en` ya pasó quedan `expirada` (B3)."""

import logging

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.repositories import alertas_repository

logger = logging.getLogger(__name__)


@celery_app.task
def expirar_alertas() -> dict:
    db = SessionLocal()
    try:
        vencidas = alertas_repository.expirar_vencidas(db)
        db.commit()
        if vencidas:
            logger.info("Alertas expiradas: %d", vencidas)
        return {"status": "ok", "expiradas": vencidas}
    finally:
        db.close()
