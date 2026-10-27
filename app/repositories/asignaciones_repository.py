from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.asignacion import Asignacion
from app.models.enums import EstadoAsignacion
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.utils.paginacion import Paginacion


def bloquear_solicitud(db: Session, solicitud_id: UUID) -> SolicitudAyuda | None:
    consulta = (
        select(SolicitudAyuda)
        .where(SolicitudAyuda.id == solicitud_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(consulta).one_or_none()


def bloquear_reporte(db: Session, reporte_id: UUID) -> Reporte | None:
    consulta = (
        select(Reporte).where(Reporte.id == reporte_id).with_for_update().execution_options(populate_existing=True)
    )
    return db.scalars(consulta).one_or_none()


def crear(
    db: Session,
    *,
    voluntario_id: UUID,
    solicitud_id: UUID | None = None,
    reporte_id: UUID | None = None,
) -> Asignacion:
    asignacion = Asignacion(
        voluntario_id=voluntario_id,
        solicitud_id=solicitud_id,
        reporte_id=reporte_id,
        estado_asignacion=EstadoAsignacion.ACTIVA,
    )
    db.add(asignacion)
    db.flush()
    db.refresh(asignacion) 
    return asignacion


def obtener_por_id(db: Session, asignacion_id: UUID) -> Asignacion | None:
    return db.get(Asignacion, asignacion_id)


def obtener_activa(
    db: Session,
    voluntario_id: UUID,
    *,
    solicitud_id: UUID | None = None,
    reporte_id: UUID | None = None,
) -> Asignacion | None:
    consulta = select(Asignacion).where(
        Asignacion.voluntario_id == voluntario_id,
        Asignacion.estado_asignacion == EstadoAsignacion.ACTIVA,
    )
    if solicitud_id is not None:
        consulta = consulta.where(Asignacion.solicitud_id == solicitud_id)
    if reporte_id is not None:
        consulta = consulta.where(Asignacion.reporte_id == reporte_id)
    return db.scalars(consulta.limit(1)).first()


def contar_activas_de_solicitud(db: Session, solicitud_id: UUID) -> int:
    consulta = (
        select(func.count())
        .select_from(Asignacion)
        .where(Asignacion.solicitud_id == solicitud_id, Asignacion.estado_asignacion == EstadoAsignacion.ACTIVA)
    )
    return db.scalar(consulta) or 0


def cancelar_activas_de_solicitud(db: Session, solicitud_id: UUID) -> int:
    """Cancela todas las asignaciones activas de la solicitud. Devuelve cuántas cambió."""
    resultado = db.execute(
        update(Asignacion)
        .where(Asignacion.solicitud_id == solicitud_id, Asignacion.estado_asignacion == EstadoAsignacion.ACTIVA)
        .values(estado_asignacion=EstadoAsignacion.CANCELADA)
        .execution_options(synchronize_session="fetch")
    )
    return resultado.rowcount


def listar_de_voluntario(
    db: Session,
    pag: Paginacion,
    *,
    voluntario_id: UUID,
    estado: EstadoAsignacion | None = None,
) -> tuple[list[Asignacion], int]:
    filtros = [Asignacion.voluntario_id == voluntario_id]
    if estado is not None:
        filtros.append(Asignacion.estado_asignacion == estado)

    total = db.scalar(select(func.count()).select_from(Asignacion).where(*filtros)) or 0
    consulta = (
        select(Asignacion)
        .where(*filtros)
        .order_by(Asignacion.asignado_en.desc(), Asignacion.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total


def actualizar_estado(db: Session, asignacion: Asignacion, *, estado: EstadoAsignacion) -> Asignacion:
    asignacion.estado_asignacion = estado
    db.flush()
    db.refresh(asignacion)
    return asignacion
