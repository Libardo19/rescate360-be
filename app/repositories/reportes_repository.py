from datetime import datetime
from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import EstadoReporte
from app.models.evidencia_reporte import EvidenciaReporte
from app.models.reporte import Reporte
from app.utils.paginacion import Paginacion

# "Efectiva" = lo que decidió una persona prevalece sobre lo que sugirió la IA
ORGANIZACION_EFECTIVA = func.coalesce(Reporte.organizacion_manual_id, Reporte.organizacion_objetivo_id)


def crear(
    db: Session,
    *,
    usuario_id: UUID,
    tipo: str,
    descripcion: str,
    ubicacion: WKTElement,
    direccion: str | None,
) -> Reporte:
    reporte = Reporte(
        usuario_id=usuario_id, tipo=tipo, descripcion=descripcion, ubicacion=ubicacion, direccion=direccion
    )
    db.add(reporte)
    db.flush()
    return reporte


def agregar_evidencia(db: Session, reporte: Reporte, *, tipo: str, ruta: str, mime: str, tamano_bytes: int) -> None:
    reporte.evidencias.append(EvidenciaReporte(tipo=tipo, ruta=ruta, mime=mime, tamano_bytes=tamano_bytes))
    db.flush()


def obtener_por_id(db: Session, reporte_id: UUID) -> Reporte | None:
    return db.get(Reporte, reporte_id)


def listar(
    db: Session,
    pag: Paginacion,
    *,
    usuario_id: UUID | None = None,
    organizacion_id: UUID | None = None,
    estado: EstadoReporte | None = None,
    tipo: str | None = None,
    tipos_fuera_de: tuple[str, ...] | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> tuple[list[Reporte], int]:
    filtros = []
    if usuario_id is not None:
        filtros.append(Reporte.usuario_id == usuario_id)
    if organizacion_id is not None:
        filtros.append(ORGANIZACION_EFECTIVA == organizacion_id)
    if estado is not None:
        filtros.append(Reporte.estado == estado)
    if tipo is not None:
        filtros.append(Reporte.tipo == tipo)
    if tipos_fuera_de is not None:
        filtros.append(Reporte.tipo.not_in(tipos_fuera_de))
    if desde is not None:
        filtros.append(Reporte.creado_en >= desde)
    if hasta is not None:
        filtros.append(Reporte.creado_en <= hasta)

    total = db.scalar(select(func.count()).select_from(Reporte).where(*filtros)) or 0
    consulta = (
        select(Reporte)
        .where(*filtros)
        .order_by(Reporte.creado_en.desc(), Reporte.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total


def actualizar(db: Session, reporte: Reporte, **campos) -> Reporte:
    for campo, valor in campos.items():
        setattr(reporte, campo, valor)
    db.flush()
    db.refresh(reporte)
    return reporte
