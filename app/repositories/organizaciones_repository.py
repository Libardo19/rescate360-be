from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import TipoOrganizacion
from app.models.organizacion import Organizacion
from app.utils.paginacion import Paginacion


def obtener_por_id(db: Session, organizacion_id: UUID) -> Organizacion | None:
    return db.get(Organizacion, organizacion_id)


def crear(db: Session, **campos) -> Organizacion:
    organizacion = Organizacion(**campos)
    db.add(organizacion)
    db.flush()
    db.refresh(organizacion)
    return organizacion


def actualizar(db: Session, organizacion: Organizacion, **campos) -> Organizacion:
    for campo, valor in campos.items():
        setattr(organizacion, campo, valor)
    db.flush()
    db.refresh(organizacion)
    return organizacion


def listar(
    db: Session,
    pag: Paginacion,
    *,
    solo_id: UUID | None = None,
    tipo: TipoOrganizacion | None = None,
    activa: bool | None = None,
    q: str | None = None,
) -> tuple[list[Organizacion], int]:
    filtros = []
    if solo_id is not None:
        filtros.append(Organizacion.id == solo_id)
    if tipo is not None:
        filtros.append(Organizacion.tipo == tipo)
    if activa is not None:
        filtros.append(Organizacion.activa == activa)
    if q:
        filtros.append(Organizacion.nombre.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(Organizacion).where(*filtros)) or 0
    consulta = (
        select(Organizacion)
        .where(*filtros)
        .order_by(Organizacion.nombre, Organizacion.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total
