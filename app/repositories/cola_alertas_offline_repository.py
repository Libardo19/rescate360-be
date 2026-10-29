from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.cola_alerta_offline import ColaAlertaOffline
from app.models.enums import MetodoEnvio
from app.utils.geo import punto_desde_latlng


def guardar_si_es_nuevo(
    db: Session,
    *,
    uuid_origen: UUID,
    usuario_id: UUID,
    tipo: str,
    payload: dict,
    lat: float,
    lng: float,
    metodo_envio: MetodoEnvio,
    generado_en: datetime,
    subido_por: UUID,
    saltos: int,
) -> UUID | None:
    """Inserta el mensaje. Si ya llegó (mismo uuid_origen, p. ej. por otro teléfono), devuelve None."""
    consulta = (
        insert(ColaAlertaOffline)
        .values(
            uuid_origen=uuid_origen,
            usuario_id=usuario_id,
            tipo=tipo,
            payload=payload,
            ubicacion=punto_desde_latlng(lat, lng),
            metodo_envio=metodo_envio,
            generado_en=generado_en,
            subido_por=subido_por,
            saltos=saltos,
        )
        .on_conflict_do_nothing(index_elements=[ColaAlertaOffline.uuid_origen])
        .returning(ColaAlertaOffline.id)
    )
    return db.scalar(consulta)


def pendientes_bloqueados(db: Session, ids: list[UUID]) -> list[ColaAlertaOffline]:
    """Los de esos ids que aún no se procesaron. SKIP LOCKED: dos workers no toman el mismo."""
    consulta = (
        select(ColaAlertaOffline)
        .where(ColaAlertaOffline.id.in_(ids), ColaAlertaOffline.sincronizado.is_(False))
        .order_by(ColaAlertaOffline.generado_en)
        .with_for_update(skip_locked=True)
    )
    return list(db.scalars(consulta).all())


def marcar_procesado(db: Session, mensaje: ColaAlertaOffline, resultado: str) -> None:
    mensaje.sincronizado = True
    mensaje.resultado = resultado
    db.flush()
