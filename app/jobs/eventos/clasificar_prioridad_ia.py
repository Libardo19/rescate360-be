"""Clasifica una solicitud de ayuda: prioridad + organización (Gemini, o reglas si no hay IA).

- Idempotente: si ya está clasificada (o el SOS ya tiene organización), no hace nada.
- El SOS no pasa por la IA para la prioridad (nace crítico), pero sí se enruta a una
  organización por reglas: sin organización, ningún voluntario lo vería.
- Nunca pisa lo que decidió una persona: la prioridad y la organización manuales
  están en otras columnas y siempre prevalecen.
"""

import logging
from uuid import UUID

from celery import shared_task

from app.core.database import SessionLocal
from app.models.enums import OrigenSolicitud, PrioridadSolicitud
from app.repositories import solicitudes_ayuda_repository as repo
from app.schemas.ia_schema import CasoIA
from app.services import clasificador_reglas, ia_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30, retry_backoff=True)
def clasificar_prioridad_ia(self, solicitud_id: str) -> dict:
    db = SessionLocal()
    try:
        solicitud = repo.obtener_para_clasificar(db, UUID(solicitud_id))
        if solicitud is None:
            logger.warning("clasificar_prioridad_ia: solicitud %s no encontrada", solicitud_id)
            return {"status": "no_encontrada", "solicitud_id": solicitud_id}

        es_sos = solicitud.origen == OrigenSolicitud.SOS
        ya_clasificada = (
            solicitud.organizacion_objetivo_id is not None
            if es_sos
            else solicitud.prioridad_ia != PrioridadSolicitud.PENDIENTE
        )
        if ya_clasificada:
            return {"status": "ya_clasificada", "solicitud_id": solicitud_id}

        caso = CasoIA(
            clase="solicitud",
            tipo=solicitud.tipo.value,
            descripcion=solicitud.descripcion,
            direccion=solicitud.direccion,
            origen=solicitud.origen.value,
        )
        organizaciones = ia_service.organizaciones_activas(db)
        if es_sos:
            enrutado = clasificador_reglas.clasificar(caso, organizaciones)
            resultado = enrutado.model_copy(update={
                "prioridad": PrioridadSolicitud.CRITICA,
                "confianza": 1.0,
                "razonamiento": "SOS: prioridad crítica automática; enrutado a la organización de rescate disponible.",
            })
        else:
            resultado = ia_service.clasificar(caso, organizaciones)

        repo.aplicar_clasificacion_ia(
            db,
            solicitud,
            prioridad_ia=resultado.prioridad,
            organizacion_objetivo_id=resultado.organizacion_id,
            confianza_ia=resultado.confianza,
            razonamiento_ia=resultado.razonamiento,
        )
        db.commit()
        logger.info(
            "Solicitud %s clasificada (%s): %s / org %s",
            solicitud_id, resultado.fuente, resultado.prioridad.value, resultado.organizacion_id,
        )
        return {
            "status": "ok",
            "solicitud_id": solicitud_id,
            "fuente": resultado.fuente,
            "prioridad_ia": resultado.prioridad.value,
            "organizacion_objetivo_id": str(resultado.organizacion_id) if resultado.organizacion_id else None,
        }
    except Exception as exc:
        # Errores de BD o del worker (la IA ya tiene su respaldo): se reintenta
        db.rollback()
        raise self.retry(exc=exc) from exc
    finally:
        db.close()
