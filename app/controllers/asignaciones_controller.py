from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import EstadoAsignacion
from app.models.usuario import Usuario
from app.schemas.asignaciones_schema import AsignacionEstadoIn, AsignacionOut
from app.services import asignaciones_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def asignar_solicitud(
    solicitud_id: UUID,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AsignacionOut:
    asignacion = asignaciones_service.tomar_solicitud(db, usuario, solicitud_id)
    return AsignacionOut.model_validate(asignacion)


def asignar_reporte(
    reporte_id: UUID,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AsignacionOut:
    asignacion = asignaciones_service.tomar_reporte(db, usuario, reporte_id)
    return AsignacionOut.model_validate(asignacion)


def listar_mias(
    estado: EstadoAsignacion | None = None,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[AsignacionOut]:
    items, total = asignaciones_service.listar_mias(db, usuario, pag, estado=estado)
    return Pagina.crear([AsignacionOut.model_validate(a) for a in items], total, pag)


def actualizar_estado(
    asignacion_id: UUID,
    datos: AsignacionEstadoIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AsignacionOut:
    asignacion = asignaciones_service.actualizar_estado(db, usuario, asignacion_id, datos)
    return AsignacionOut.model_validate(asignacion)
