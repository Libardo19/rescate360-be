"""Conteos del dashboard. `organizacion_id=None` = todo el sistema (super admin)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alerta import Alerta
from app.models.asignacion import Asignacion
from app.models.centro_ayuda import CentroAyuda
from app.models.enums import (
    EstadoAsignacion,
    EstadoCasoPersona,
    EstadoReporte,
    EstadoSolicitud,
    EstadoUsuario,
    RolUsuario,
)
from app.models.organizacion import Organizacion
from app.models.persona_desaparecida import PersonaDesaparecida
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.models.usuario import Usuario
from app.repositories.reportes_repository import ORGANIZACION_EFECTIVA as ORG_REPORTE

SOLICITUDES_ACTIVAS = (EstadoSolicitud.PENDIENTE, EstadoSolicitud.EN_PROCESO)
ORG_SOLICITUD = func.coalesce(SolicitudAyuda.organizacion_manual_id, SolicitudAyuda.organizacion_objetivo_id)
# Las alertas todavía no tienen estado ni vencimiento (llegan con B3): mientras tanto,
# "activa" = creada en las últimas 24 horas
VIGENCIA_ALERTA = timedelta(hours=24)


def _contar(db: Session, modelo, *filtros) -> int:
    return db.scalar(select(func.count()).select_from(modelo).where(*filtros)) or 0


def reportes_pendientes(db: Session, organizacion_id: UUID | None) -> int:
    filtros = [Reporte.estado == EstadoReporte.PENDIENTE]
    if organizacion_id is not None:
        filtros.append(ORG_REPORTE == organizacion_id)
    return _contar(db, Reporte, *filtros)


def solicitudes_activas(db: Session, organizacion_id: UUID | None) -> int:
    filtros = [SolicitudAyuda.estado.in_(SOLICITUDES_ACTIVAS)]
    if organizacion_id is not None:
        filtros.append(ORG_SOLICITUD == organizacion_id)
    return _contar(db, SolicitudAyuda, *filtros)


def alertas_activas(db: Session, organizacion_id: UUID | None) -> int:
    filtros = [Alerta.creado_en >= datetime.now(UTC) - VIGENCIA_ALERTA]
    if organizacion_id is not None:
        filtros.append(Alerta.organizacion_id == organizacion_id)
    return _contar(db, Alerta, *filtros)


def centros_registrados(db: Session, organizacion_id: UUID | None) -> int:
    filtros = [CentroAyuda.estado == "activo"]
    if organizacion_id is not None:
        filtros.append(CentroAyuda.organizacion_id == organizacion_id)
    return _contar(db, CentroAyuda, *filtros)


def personas_buscando(db: Session) -> int:
    # Las fichas no son de una organización: el número es el mismo para todos
    return _contar(db, PersonaDesaparecida, PersonaDesaparecida.estado_caso == EstadoCasoPersona.BUSCANDO)


def voluntarios_activos(db: Session, organizacion_id: UUID | None) -> int:
    filtros = [Usuario.rol == RolUsuario.VOLUNTARIO, Usuario.estado == EstadoUsuario.ACTIVO]
    if organizacion_id is not None:
        filtros.append(Usuario.organizacion_id == organizacion_id)
    return _contar(db, Usuario, *filtros)


def tareas_activas_de(db: Session, voluntario_id: UUID) -> int:
    return _contar(
        db,
        Asignacion,
        Asignacion.voluntario_id == voluntario_id,
        Asignacion.estado_asignacion == EstadoAsignacion.ACTIVA,
    )


def solicitudes_recientes(db: Session, organizacion_id: UUID | None, limite: int) -> list[SolicitudAyuda]:
    consulta = select(SolicitudAyuda).order_by(SolicitudAyuda.creado_en.desc()).limit(limite)
    if organizacion_id is not None:
        consulta = consulta.where(ORG_SOLICITUD == organizacion_id)
    return list(db.scalars(consulta))


def reportes_recientes(db: Session, organizacion_id: UUID | None, limite: int) -> list[Reporte]:
    consulta = select(Reporte).order_by(Reporte.creado_en.desc()).limit(limite)
    if organizacion_id is not None:
        consulta = consulta.where(ORG_REPORTE == organizacion_id)
    return list(db.scalars(consulta))


def totales_por_organizacion(db: Session) -> list[dict]:
    """Organizaciones activas con sus casos abiertos y voluntarios (dos GROUP BY, no una consulta por fila)."""
    reportes = dict(
        db.execute(
            select(ORG_REPORTE, func.count())
            .where(Reporte.estado == EstadoReporte.PENDIENTE, ORG_REPORTE.is_not(None))
            .group_by(ORG_REPORTE)
        ).all()
    )
    solicitudes = dict(
        db.execute(
            select(ORG_SOLICITUD, func.count())
            .where(SolicitudAyuda.estado.in_(SOLICITUDES_ACTIVAS), ORG_SOLICITUD.is_not(None))
            .group_by(ORG_SOLICITUD)
        ).all()
    )
    voluntarios = dict(
        db.execute(
            select(Usuario.organizacion_id, func.count())
            .where(Usuario.rol == RolUsuario.VOLUNTARIO, Usuario.estado == EstadoUsuario.ACTIVO)
            .group_by(Usuario.organizacion_id)
        ).all()
    )
    organizaciones = db.scalars(select(Organizacion).where(Organizacion.activa.is_(True)).order_by(Organizacion.nombre))
    return [
        {
            "organizacion_id": org.id,
            "nombre": org.nombre,
            "reportes_pendientes": reportes.get(org.id, 0),
            "solicitudes_activas": solicitudes.get(org.id, 0),
            "voluntarios_activos": voluntarios.get(org.id, 0),
        }
        for org in organizaciones
    ]


def sin_organizacion(db: Session) -> int:
    """Casos abiertos que la IA no pudo enrutar y nadie asignó: el super admin los debe mover."""
    return _contar(
        db, Reporte, Reporte.estado == EstadoReporte.PENDIENTE, ORG_REPORTE.is_(None)
    ) + _contar(db, SolicitudAyuda, SolicitudAyuda.estado.in_(SOLICITUDES_ACTIVAS), ORG_SOLICITUD.is_(None))
