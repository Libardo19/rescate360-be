from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.alerta import Alerta
from app.models.enums import EstadoAlerta, EstadoUsuario, NivelAlerta
from app.models.usuario import Usuario
from app.utils.geo import cerca_de, circulo_a_poligono, punto_desde_latlng
from app.utils.paginacion import Paginacion


def crear(
    db: Session,
    *,
    titulo: str,
    tipo: str,
    mensaje: str,
    nivel: NivelAlerta,
    lat: float,
    lng: float,
    radio_m: float,
    expira_en: datetime,
    creado_por: UUID,
    organizacion_id: UUID | None,
    origen: str = "manual",
) -> Alerta:
    alerta = Alerta(
        titulo=titulo,
        tipo=tipo,
        mensaje=mensaje,
        nivel=nivel,
        origen=origen,
        centro=punto_desde_latlng(lat, lng),
        radio_m=radio_m,
        zona_afectada=circulo_a_poligono(lat, lng, radio_m),
        expira_en=expira_en,
        creado_por=creado_por,
        organizacion_id=organizacion_id,
    )
    db.add(alerta)
    db.flush()
    db.refresh(alerta)
    return alerta


def obtener_por_id(db: Session, alerta_id: UUID) -> Alerta | None:
    return db.get(Alerta, alerta_id)


def bloquear(db: Session, alerta_id: UUID) -> Alerta | None:
    consulta = select(Alerta).where(Alerta.id == alerta_id).with_for_update().execution_options(populate_existing=True)
    return db.scalars(consulta).one_or_none()


def listar(
    db: Session,
    pag: Paginacion,
    *,
    estados: tuple[EstadoAlerta, ...],
    punto: tuple[float, float] | None = None,
    organizacion_id: UUID | None = None,
) -> tuple[list[Alerta], int]:
    """`punto` = solo las alertas cuyo círculo lo contiene (las que me afectan)."""
    filtros = [Alerta.estado.in_(estados)]
    if punto is not None:
        filtros.append(cerca_de(Alerta.zona_afectada, punto[0], punto[1], 0))
    if organizacion_id is not None:
        filtros.append(Alerta.organizacion_id == organizacion_id)
    total = db.scalar(select(func.count()).select_from(Alerta).where(*filtros)) or 0
    consulta = (
        select(Alerta)
        .where(*filtros)
        .order_by(Alerta.creado_en.desc(), Alerta.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total


def actualizar(db: Session, alerta: Alerta, **campos) -> Alerta:
    for campo, valor in campos.items():
        setattr(alerta, campo, valor)
    db.flush()
    db.refresh(alerta)
    return alerta


def usuarios_en_la_zona(db: Session, alerta: Alerta, horas_ubicacion: int) -> list[UUID]:
    """Usuarios activos cuya ubicación reciente cae dentro del círculo de la alerta."""
    limite = datetime.now(UTC) - timedelta(hours=horas_ubicacion)
    consulta = select(Usuario.id).where(
        Usuario.estado == EstadoUsuario.ACTIVO,
        Usuario.ubicacion_actual.is_not(None),
        Usuario.ubicacion_actualizada_en >= limite,
        func.ST_Intersects(Usuario.ubicacion_actual, alerta.zona_afectada),
    )
    return list(db.scalars(consulta))


def expirar_vencidas(db: Session) -> int:
    resultado = db.execute(
        update(Alerta)
        .where(Alerta.estado == EstadoAlerta.ACTIVA, Alerta.expira_en <= datetime.now(UTC))
        .values(estado=EstadoAlerta.EXPIRADA)
    )
    return resultado.rowcount or 0
