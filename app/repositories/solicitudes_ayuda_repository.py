from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import EstadoSolicitud, OrigenSolicitud, PrioridadSolicitud, TipoSolicitud
from app.models.solicitud_ayuda import SolicitudAyuda
from app.utils.paginacion import Paginacion

# "Efectivo" = lo que decidió una persona prevalece sobre lo que sugirió la IA
_ORGANIZACION_EFECTIVA = func.coalesce(SolicitudAyuda.organizacion_manual_id, SolicitudAyuda.organizacion_objetivo_id)
_PRIORIDAD_EFECTIVA = func.coalesce(SolicitudAyuda.prioridad_manual, SolicitudAyuda.prioridad_ia)


def crear(db: Session, *,
    usuario_id: UUID,
    descripcion: str,
    tipo: TipoSolicitud,
    ubicacion: WKTElement,
    origen: OrigenSolicitud,
    prioridad_ia: PrioridadSolicitud,
    direccion: str | None = None,
) -> SolicitudAyuda:
    solicitud = SolicitudAyuda(
        usuario_id=usuario_id, descripcion=descripcion, tipo=tipo, ubicacion=ubicacion,
        origen=origen, prioridad_ia=prioridad_ia, direccion=direccion,
    )
    db.add(solicitud)
    db.flush()
    db.refresh(solicitud)
    return solicitud


def obtener_por_id(db: Session, solicitud_id: UUID) -> SolicitudAyuda | None:
    return db.get(SolicitudAyuda, solicitud_id)


def listar(
    db: Session,
    pag: Paginacion,
    *,
    usuario_id: UUID | None = None,
    organizacion_id: UUID | None = None,
    estado: EstadoSolicitud | None = None,
    tipo: TipoSolicitud | None = None,
    prioridad: PrioridadSolicitud | None = None,
) -> tuple[list[SolicitudAyuda], int]:
    filtros = []
    if usuario_id is not None:
        filtros.append(SolicitudAyuda.usuario_id == usuario_id)
    if organizacion_id is not None:
        filtros.append(_ORGANIZACION_EFECTIVA == organizacion_id)
    if estado is not None:
        filtros.append(SolicitudAyuda.estado == estado)
    if tipo is not None:
        filtros.append(SolicitudAyuda.tipo == tipo)
    if prioridad is not None:
        filtros.append(_PRIORIDAD_EFECTIVA == prioridad)

    total = db.scalar(select(func.count()).select_from(SolicitudAyuda).where(*filtros)) or 0
    consulta = (
        select(SolicitudAyuda)
        .where(*filtros)
        .order_by(SolicitudAyuda.creado_en.desc(), SolicitudAyuda.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total


def actualizar_prioridad(
    db: Session, solicitud: SolicitudAyuda, *, prioridad_manual: PrioridadSolicitud, modificado_por: UUID
) -> SolicitudAyuda:
    solicitud.prioridad_manual = prioridad_manual
    solicitud.modificado_por = modificado_por
    db.flush()
    db.refresh(solicitud)
    return solicitud


def actualizar_estado(
    db: Session, solicitud: SolicitudAyuda, *, estado: EstadoSolicitud, modificado_por: UUID
) -> SolicitudAyuda:
    solicitud.estado = estado
    solicitud.modificado_por = modificado_por
    db.flush()
    db.refresh(solicitud)
    return solicitud


def actualizar_organizacion(
    db: Session, solicitud: SolicitudAyuda, *, organizacion_id: UUID, modificado_por: UUID
) -> SolicitudAyuda:
    solicitud.organizacion_manual_id = organizacion_id
    solicitud.modificado_por = modificado_por
    db.flush()
    db.refresh(solicitud)
    return solicitud
