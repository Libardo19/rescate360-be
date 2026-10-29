from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.evento_sismico import EventoSismico
from app.utils.geo import distancia_m, punto_desde_latlng
from app.utils.paginacion import Paginacion


def registrar(
    db: Session,
    *,
    id_externo: str,
    fuente: str,
    magnitud: float,
    profundidad_km: float | None,
    lugar: str,
    lat: float,
    lng: float,
    ocurrido_en: datetime,
    radio_afectacion_m: float,
) -> tuple[EventoSismico, bool]:
    """Inserta el sismo si no existe (por id_externo). Devuelve (evento, es_nuevo)."""
    consulta = (
        insert(EventoSismico)
        .values(
            id_externo=id_externo,
            fuente=fuente,
            magnitud=magnitud,
            profundidad_km=profundidad_km,
            lugar=lugar,
            epicentro=punto_desde_latlng(lat, lng),
            ocurrido_en=ocurrido_en,
            radio_afectacion_m=radio_afectacion_m,
        )
        .on_conflict_do_nothing(index_elements=[EventoSismico.id_externo])
        .returning(EventoSismico.id)
    )
    nuevo_id = db.scalar(consulta)
    if nuevo_id is not None:
        return db.get(EventoSismico, nuevo_id), True
    existente = db.scalar(select(EventoSismico).where(EventoSismico.id_externo == id_externo))
    return existente, False


def obtener_por_id(db: Session, evento_id: UUID) -> EventoSismico | None:
    return db.get(EventoSismico, evento_id)


def listar(
    db: Session, pag: Paginacion, *, desde: datetime | None, magnitud_min: float | None
) -> tuple[list[EventoSismico], int]:
    filtros = []
    if desde is not None:
        filtros.append(EventoSismico.ocurrido_en >= desde)
    if magnitud_min is not None:
        filtros.append(EventoSismico.magnitud >= magnitud_min)
    total = db.scalar(select(func.count()).select_from(EventoSismico).where(*filtros)) or 0
    consulta = (
        select(EventoSismico)
        .where(*filtros)
        .order_by(EventoSismico.ocurrido_en.desc(), EventoSismico.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total


def distancia_a(db: Session, evento: EventoSismico, lat: float, lng: float) -> float:
    consulta = select(distancia_m(EventoSismico.epicentro, lat, lng)).where(EventoSismico.id == evento.id)
    return float(db.scalar(consulta))


def recientes_para_mapa(
    db: Session, *, ocurrido_desde: datetime, registrado_desde: datetime | None, limite: int
) -> list[EventoSismico]:
    """Sismos ocurridos desde `ocurrido_desde`. En el polling, solo los registrados después de
    `registrado_desde` (el feed publica con unos minutos de retraso: no se filtra por ocurrido_en)."""
    filtros = [EventoSismico.ocurrido_en >= ocurrido_desde]
    if registrado_desde is not None:
        filtros.append(EventoSismico.creado_en > registrado_desde)
    consulta = (
        select(EventoSismico)
        .where(*filtros)
        .order_by(EventoSismico.ocurrido_en.desc())
        .limit(limite)
    )
    return list(db.scalars(consulta).all())
