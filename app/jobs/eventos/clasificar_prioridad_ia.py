import logging
from uuid import UUID

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.integrations import ia_client
from app.models.enums import OrigenSolicitud, PrioridadSolicitud
from app.models.organizacion import Organizacion
from app.repositories import solicitudes_ayuda_repository as repo

logger = logging.getLogger(__name__)


def _buscar_organizacion_match(db: Session, nombre_sugerido: str | None) -> UUID | None:
    if not nombre_sugerido:
        return None

    nombre_limpio = " ".join(nombre_sugerido.strip().lower().split())

    organizaciones = db.scalars(select(Organizacion).where(Organizacion.activa.is_(True))).all()

    for org in organizaciones:
        nombre_org = " ".join((org.nombre or "").strip().lower().split())
        if nombre_org == nombre_limpio:
            return org.id

    for org in organizaciones:
        nombre_org = " ".join((org.nombre or "").strip().lower().split())
        if nombre_limpio and nombre_org and (nombre_limpio in nombre_org or nombre_org in nombre_limpio):
            if len(nombre_limpio) >= 4 and len(nombre_org) >= 4:
                return org.id

    return None


@shared_task(bind=True, max_retries=3, default_retry_delay=60, retry_backoff=True)
def clasificar_prioridad_ia(self, solicitud_id: str) -> dict:
    db: Session = SessionLocal()
    try:
        solicitud_uuid = UUID(solicitud_id)
        solicitud = repo.obtener_para_clasificar(db, solicitud_uuid)
        if solicitud is None:
            logger.warning("clasificar_prioridad_ia: solicitud %s no encontrada", solicitud_id)
            return {"status": "no_encontrada", "solicitud_id": solicitud_id}

        if solicitud.origen == OrigenSolicitud.SOS:
            logger.info("clasificar_prioridad_ia: solicitud %s es SOS, se omite IA", solicitud_id)
            return {"status": "omitida_sos", "solicitud_id": solicitud_id}

        if solicitud.prioridad_ia != PrioridadSolicitud.PENDIENTE:
            logger.info("clasificar_prioridad_ia: solicitud %s ya clasificada, idempotente", solicitud_id)
            return {"status": "ya_clasificada", "solicitud_id": solicitud_id}

        organizaciones = db.scalars(select(Organizacion).where(Organizacion.activa.is_(True))).all()
        orgs_lista = []
        for org in organizaciones:
            tipo_val = org.tipo.value if hasattr(org.tipo, "value") else str(org.tipo)
            orgs_lista.append({"id": str(org.id), "nombre": org.nombre, "tipo": tipo_val})

        try:
            resultado = ia_client.clasificar_solicitud(
                tipo=solicitud.tipo.value if hasattr(solicitud.tipo, "value") else str(solicitud.tipo),
                descripcion=solicitud.descripcion,
                direccion=solicitud.direccion,
                origen=solicitud.origen.value if hasattr(solicitud.origen, "value") else str(solicitud.origen),
                organizaciones_activas=orgs_lista,
            )
        except Exception as exc:
            logger.warning("clasificar_prioridad_ia fallo intento %s para %s: %s", self.request.retries + 1, solicitud_id, exc)
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc)
            logger.error("clasificar_prioridad_ia agotados reintentos para %s, dejando en PENDIENTE", solicitud_id)
            return {"status": "fallback_pendiente", "solicitud_id": solicitud_id}

        organizacion_objetivo_id = _buscar_organizacion_match(db, resultado.organizacion_sugerida)

        repo.aplicar_clasificacion_ia(
            db,
            solicitud,
            prioridad_ia=resultado.prioridad,
            organizacion_objetivo_id=organizacion_objetivo_id,
            confianza_ia=resultado.confianza,
            razonamiento_ia=resultado.razonamiento,
        )
        db.commit()
        logger.info("clasificar_prioridad_ia completado para %s -> %s / org:%s", solicitud_id, resultado.prioridad.value, organizacion_objetivo_id)
        return {"status": "ok", "solicitud_id": solicitud_id, "prioridad_ia": resultado.prioridad.value, "organizacion_objetivo_id": str(organizacion_objetivo_id) if organizacion_objetivo_id else None}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
