"""Procesa los mensajes sin conexión que llegaron por /offline/sync o /offline/relevo (B7).

Idempotente: cada mensaje se procesa una sola vez (`sincronizado`) y el mismo lote enviado dos
veces no se guarda dos veces (único por `uuid_origen`).
"""

from uuid import UUID

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services import offline_service


@celery_app.task
def procesar_lote_offline(ids: list[str]) -> dict:
    db = SessionLocal()
    try:
        resultados = offline_service.procesar_ids(db, [UUID(i) for i in ids])
        return {"status": "ok", "procesados": len(resultados), "resultados": resultados}
    finally:
        db.close()
