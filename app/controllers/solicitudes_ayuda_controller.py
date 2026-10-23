"""HTTP de solicitudes_ayuda: arma la respuesta y llama al service. Sin SQL ni reglas."""

from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import EstadoSolicitud, PrioridadSolicitud, TipoSolicitud
from app.models.usuario import Usuario
from app.schemas.solicitudes_ayuda_schema import (
    SolicitudAyudaIn,
    SolicitudAyudaOut,
    SolicitudEstadoIn,
    SolicitudPrioridadIn,
    SolicitudSOSIn,
)
from app.services import solicitudes_ayuda_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def crear_solicitud(
    datos: SolicitudAyudaIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SolicitudAyudaOut:
    solicitud = solicitudes_ayuda_service.crear_solicitud(db, usuario, datos)
    return SolicitudAyudaOut.model_validate(solicitud)


def crear_sos(
    datos: SolicitudSOSIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SolicitudAyudaOut:
    solicitud = solicitudes_ayuda_service.crear_sos(db, usuario, datos)
    return SolicitudAyudaOut.model_validate(solicitud)


def listar_solicitudes(
    estado: EstadoSolicitud | None = None,
    tipo: TipoSolicitud | None = None,
    prioridad: PrioridadSolicitud | None = None,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[SolicitudAyudaOut]:
    items, total = solicitudes_ayuda_service.listar_solicitudes(
        db, usuario, pag, estado=estado, tipo=tipo, prioridad=prioridad
    )
    return Pagina.crear([SolicitudAyudaOut.model_validate(s) for s in items], total, pag)


def obtener_solicitud(
    solicitud_id: UUID,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SolicitudAyudaOut:
    solicitud = solicitudes_ayuda_service.obtener_solicitud(db, usuario, solicitud_id)
    return SolicitudAyudaOut.model_validate(solicitud)


def actualizar_prioridad(
    solicitud_id: UUID,
    datos: SolicitudPrioridadIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SolicitudAyudaOut:
    solicitud = solicitudes_ayuda_service.actualizar_prioridad(db, usuario, solicitud_id, datos)
    return SolicitudAyudaOut.model_validate(solicitud)


def actualizar_estado(
    solicitud_id: UUID,
    datos: SolicitudEstadoIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SolicitudAyudaOut:
    solicitud = solicitudes_ayuda_service.actualizar_estado(db, usuario, solicitud_id, datos)
    return SolicitudAyudaOut.model_validate(solicitud)
