from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.models.centro_ayuda import CentroAyuda
from app.utils.paginacion import Paginacion


def crear(
    db: Session,
    *,
    nombre: str,
    tipo: str,
    estado: str,
    direccion: str | None,
    ubicacion: WKTElement,
    recursos_disponibles: str | None,
    gestionado_por: UUID,
    organizacion_id: UUID | None,
) -> CentroAyuda:
    centro = CentroAyuda(
        nombre=nombre,
        tipo=tipo,
        estado=estado,
        direccion=direccion,
        ubicacion=ubicacion,
        recursos_disponibles=recursos_disponibles,
        gestionado_por=gestionado_por,
        organizacion_id=organizacion_id,
    )
    db.add(centro)
    db.flush()
    db.refresh(centro)
    return centro


def obtener_por_id(db: Session, centro_id: UUID) -> CentroAyuda | None:
    return db.get(CentroAyuda, centro_id)


def listar(
    db: Session,
    pag: Paginacion | None = None,
    *,
    tipo: str | None = None,
    q: str | None = None,
    estado: str | None = None,
    organizacion_id: UUID | None = None,
    incluir_solo_activos: bool = False,
    solo_mis_centros: bool = False,
    ver_tambien_otros: bool = False,
    lat: float | None = None,
    lng: float | None = None,
    radio_m: float | None = None,
) -> tuple[list[tuple[CentroAyuda, float | None]], int]:
    filtros = []
    if incluir_solo_activos:
        filtros.append(CentroAyuda.estado != 'inactivo')

    if tipo is not None:
        filtros.append(CentroAyuda.tipo == tipo)
    if estado is not None:
        filtros.append(CentroAyuda.estado == estado)
    if q is not None and q.strip():
        patron = f"%{q.strip().lower()}%"
        filtros.append(
            func.lower(func.coalesce(CentroAyuda.nombre, '')).like(patron)
            | func.lower(func.coalesce(CentroAyuda.direccion, '')).like(patron)
        )

    if organizacion_id is not None and solo_mis_centros and not ver_tambien_otros:
        filtros.append(CentroAyuda.organizacion_id == organizacion_id)
    # Si ver_tambien_otros es True, no aplicamos restricción exclusiva a mis centros; se muestran todos los visibles

    punto = None
    if lat is not None and lng is not None:
        punto = WKTElement(f'POINT({lng} {lat})', srid=4326)

    if punto is not None and radio_m is not None:
        filtros.append(func.ST_DWithin(CentroAyuda.ubicacion.cast(func.geography), func.cast(punto, func.geography), radio_m))

    if punto is not None:
        distancia = func.ST_DistanceSphere(CentroAyuda.ubicacion, punto)
        consulta = select(CentroAyuda, distancia).where(*filtros)
        consulta = consulta.order_by(distancia.asc())
    else:
        consulta = select(CentroAyuda, literal(None)).where(*filtros)
        consulta = consulta.order_by(CentroAyuda.nombre.asc())

    if pag is not None:
        total = db.scalar(select(func.count()).select_from(CentroAyuda).where(*filtros)) or 0
        consulta = consulta.offset(pag.offset).limit(pag.por_pagina)
        filas = db.execute(consulta).all()
        return [(fila[0], float(fila[1]) if fila[1] is not None else None) for fila in filas], total
    else:
        total = db.scalar(select(func.count()).select_from(CentroAyuda).where(*filtros)) or 0
        filas = db.execute(consulta).all()
        return [(fila[0], float(fila[1]) if fila[1] is not None else None) for fila in filas], total


def actualizar(db: Session, centro: CentroAyuda, **campos) -> CentroAyuda:
    for campo, valor in campos.items():
        setattr(centro, campo, valor)
    db.flush()
    db.refresh(centro)
    return centro
