from datetime import date
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.campana import Campana
from app.models.donacion import Donacion
from app.models.enums import EstadoDonacion
from app.utils.paginacion import Paginacion


def crear_campana(db: Session, **campos) -> Campana:
    campana = Campana(**campos)
    db.add(campana)
    db.flush()
    db.refresh(campana)
    return campana


def obtener_campana(db: Session, campana_id: UUID) -> Campana | None:
    return db.get(Campana, campana_id)


def listar_campanas(
    db: Session, *, solo_vigentes: bool, organizacion_id: UUID | None
) -> list[Campana]:
    filtros = []
    if solo_vigentes:
        filtros += [Campana.activa.is_(True), Campana.fecha_fin >= date.today()]
    if organizacion_id is not None:
        filtros.append(Campana.organizacion_id == organizacion_id)
    consulta = select(Campana).where(*filtros).order_by(Campana.fecha_fin, Campana.titulo)
    return list(db.scalars(consulta).all())


def recaudado_por_campana(db: Session, campana_ids: list[UUID]) -> dict[UUID, float]:
    """En dinero suma el monto; en lo demás, la cantidad."""
    if not campana_ids:
        return {}
    valor = case((Donacion.categoria == "dinero", Donacion.monto), else_=Donacion.cantidad)
    consulta = (
        select(Donacion.campana_id, func.coalesce(func.sum(valor), 0))
        .where(Donacion.campana_id.in_(campana_ids))
        .group_by(Donacion.campana_id)
    )
    return {campana_id: float(total) for campana_id, total in db.execute(consulta).all()}


def actualizar(db: Session, registro, **campos):
    for campo, valor in campos.items():
        setattr(registro, campo, valor)
    db.flush()
    db.refresh(registro)
    return registro


def crear_donacion(db: Session, **campos) -> Donacion:
    donacion = Donacion(**campos)
    db.add(donacion)
    db.flush()
    db.refresh(donacion)
    return donacion


def obtener_donacion(db: Session, donacion_id: UUID) -> Donacion | None:
    return db.get(Donacion, donacion_id)


def listar_donaciones(
    db: Session,
    pag: Paginacion,
    *,
    organizacion_id: UUID | None,
    categoria: str | None,
    estado: EstadoDonacion | None,
    campana_id: UUID | None,
) -> tuple[list[Donacion], int]:
    filtros = []
    if organizacion_id is not None:
        filtros.append(Donacion.organizacion_id == organizacion_id)
    if categoria is not None:
        filtros.append(Donacion.categoria == categoria)
    if estado is not None:
        filtros.append(Donacion.estado == estado)
    if campana_id is not None:
        filtros.append(Donacion.campana_id == campana_id)
    total = db.scalar(select(func.count()).select_from(Donacion).where(*filtros)) or 0
    consulta = (
        select(Donacion)
        .where(*filtros)
        .order_by(Donacion.creado_en.desc(), Donacion.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total
