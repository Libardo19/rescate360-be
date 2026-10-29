"""Reservado (B6). Hoy no hace falta: GET /dashboard calcula los números en el momento y con los
índices actuales responde rápido. Si el volumen crece, aquí se precalcularían por organización.
"""

from app.core.celery_app import celery_app


@celery_app.task
def recalcular_estadisticas() -> dict:
    return {"status": "sin_cambios"}
