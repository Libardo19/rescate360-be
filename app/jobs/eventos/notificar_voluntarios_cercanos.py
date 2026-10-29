"""Push a los voluntarios cercanos de la organización que recibió un reporte (B3).

Se encola cuando el reporte ya tiene organización: al terminar la clasificación de la IA o
cuando el super admin lo enruta a mano. Sin organización no hay a quién avisar.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.enums import EstadoReporte, EstadoUsuario, RolUsuario
from app.models.reporte import Reporte
from app.models.usuario import Usuario
from app.schemas.reportes_schema import etiqueta_tipo
from app.services import notificaciones_service
from app.utils.geo import cerca_de, latlng_desde_punto

logger = logging.getLogger(__name__)

RADIO_M = 5_000
HORAS_UBICACION = 24


@celery_app.task
def notificar_voluntarios_cercanos(reporte_id: str) -> dict:
    db = SessionLocal()
    try:
        reporte = db.get(Reporte, UUID(reporte_id))
        if reporte is None or reporte.estado not in (EstadoReporte.PENDIENTE, EstadoReporte.VERIFICADO):
            return {"status": "no_aplica", "reporte_id": reporte_id}
        # Organización efectiva (la manual prevalece); no se importa reportes_service: lo importa a este job
        organizacion_id = reporte.organizacion_manual_id or reporte.organizacion_objetivo_id
        if organizacion_id is None:
            return {"status": "sin_organizacion", "reporte_id": reporte_id}

        punto = latlng_desde_punto(reporte.ubicacion)
        limite = datetime.now(UTC) - timedelta(hours=HORAS_UBICACION)
        voluntarios = list(
            db.scalars(
                select(Usuario.id).where(
                    Usuario.rol == RolUsuario.VOLUNTARIO,
                    Usuario.estado == EstadoUsuario.ACTIVO,
                    Usuario.organizacion_id == organizacion_id,
                    Usuario.ubicacion_actualizada_en >= limite,
                    cerca_de(Usuario.ubicacion_actual, punto["lat"], punto["lng"], RADIO_M),
                )
            )
        )
        dispositivos = notificaciones_service.notificar_usuarios(
            db,
            voluntarios,
            titulo=f"Reporte cerca de ti: {etiqueta_tipo(reporte.tipo)}",
            cuerpo=reporte.descripcion[:140],
            datos={"tipo": "reporte", "reporte_id": reporte_id},
        )
        return {"status": "ok", "reporte_id": reporte_id, "voluntarios": len(voluntarios), "dispositivos": dispositivos}
    finally:
        db.close()
