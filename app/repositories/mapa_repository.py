"""Consultas del mapa. El filtro por distancia usa `cerca_de` (geography, en metros)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import EstadoReporte, EstadoSolicitud
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.utils.geo import cerca_de

# Tope de puntos por capa en una respuesta: el mapa no necesita más y protege la API
MAXIMO_POR_CAPA = 500

SOLICITUDES_ABIERTAS = (EstadoSolicitud.PENDIENTE, EstadoSolicitud.EN_PROCESO)
REPORTES_ABIERTOS = (EstadoReporte.PENDIENTE, EstadoReporte.VERIFICADO)


def _filtros_comunes(modelo, abiertos, *, centro, radio_m, desde) -> list:
    filtros = []
    if centro is not None:
        filtros.append(cerca_de(modelo.ubicacion, centro[0], centro[1], radio_m))
    # Sin `desde` se pinta el mapa completo (solo lo abierto). Con `desde` llega todo lo que
    # cambió, también lo que se cerró, para que el cliente lo quite.
    if desde is None:
        filtros.append(modelo.estado.in_(abiertos))
    else:
        filtros.append(modelo.actualizado_en > desde)
    return filtros


def listar_solicitudes(
    db: Session, *, centro: tuple[float, float] | None, radio_m: float, desde: datetime | None
) -> list[SolicitudAyuda]:
    filtros = _filtros_comunes(SolicitudAyuda, SOLICITUDES_ABIERTAS, centro=centro, radio_m=radio_m, desde=desde)
    consulta = (
        select(SolicitudAyuda)
        .where(*filtros)
        .order_by(SolicitudAyuda.actualizado_en.desc())
        .limit(MAXIMO_POR_CAPA)
    )
    return list(db.scalars(consulta).all())


def listar_reportes(
    db: Session,
    *,
    centro: tuple[float, float] | None,
    radio_m: float,
    desde: datetime | None,
    usuario_id: UUID,
    organizacion_id: UUID | None,
    todos: bool,
) -> list[Reporte]:
    """Un reporte sin verificar solo lo ve quien lo hizo, su organización y el super admin.
    Los verificados son información pública."""
    filtros = _filtros_comunes(Reporte, REPORTES_ABIERTOS, centro=centro, radio_m=radio_m, desde=desde)
    if not todos:
        visibles = [Reporte.estado == EstadoReporte.VERIFICADO, Reporte.usuario_id == usuario_id]
        if organizacion_id is not None:
            organizacion_efectiva = func.coalesce(Reporte.organizacion_manual_id, Reporte.organizacion_objetivo_id)
            visibles.append(organizacion_efectiva == organizacion_id)
        filtros.append(or_(*visibles))
    consulta = select(Reporte).where(*filtros).order_by(Reporte.actualizado_en.desc()).limit(MAXIMO_POR_CAPA)
    return list(db.scalars(consulta).all())

