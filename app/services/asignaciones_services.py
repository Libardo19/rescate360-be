from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import Conflicto, NoEncontrado, SinPermiso
from app.middlewares.role_middleware import verificar_misma_organizacion
from app.models.asignacion import Asignacion
from app.models.enums import EstadoAsignacion, EstadoSolicitud
from app.models.solicitud_ayuda import SolicitudAyuda
from app.models.usuario import Usuario
from app.repositories import asignaciones_repository as repo
from app.repositories import solicitudes_ayuda_repository as solicitudes_repo
from app.schemas.asignaciones_schema import AsignacionEstadoIn
from app.services import solicitudes_ayuda_service as solicitudes_service
from app.utils.paginacion import Paginacion

ESTADOS_CERRADOS = (EstadoSolicitud.ATENDIDA, EstadoSolicitud.CANCELADA)


def estado_solicitud_tras_cambio(
    estado_solicitud: EstadoSolicitud,
    nuevo_estado: EstadoAsignacion,
    activas_restantes: int,
) -> EstadoSolicitud | None:

    if nuevo_estado == EstadoAsignacion.FINALIZADA and estado_solicitud in (
        EstadoSolicitud.PENDIENTE,
        EstadoSolicitud.EN_PROCESO,
    ):
        return EstadoSolicitud.ATENDIDA
    if (
        nuevo_estado == EstadoAsignacion.CANCELADA
        and estado_solicitud == EstadoSolicitud.EN_PROCESO
        and activas_restantes == 0
    ):
        return EstadoSolicitud.PENDIENTE
    return None


def tomar_solicitud(db: Session, usuario: Usuario, solicitud_id: UUID) -> Asignacion:
    solicitud = repo.bloquear_solicitud(db, solicitud_id)
    if solicitud is None:
        raise NoEncontrado("La solicitud no existe", codigo="SOLICITUD_NO_ENCONTRADA")

    solicitudes_service.verificar_acceso(usuario, solicitud)

    if solicitud.estado in ESTADOS_CERRADOS:
        raise Conflicto("La solicitud ya está cerrada", codigo="SOLICITUD_CERRADA")
    if repo.obtener_activa(db, usuario.id, solicitud_id=solicitud.id) is not None:
        raise Conflicto("Ya tienes esta solicitud asignada", codigo="ASIGNACION_DUPLICADA")

    asignacion = repo.crear(db, voluntario_id=usuario.id, solicitud_id=solicitud.id)
    if solicitud.estado == EstadoSolicitud.PENDIENTE:
        solicitudes_repo.actualizar_estado(
            db, solicitud, estado=EstadoSolicitud.EN_PROCESO, modificado_por=usuario.id
        )
    db.commit()
    return asignacion


def tomar_reporte(db: Session, usuario: Usuario, reporte_id: UUID) -> Asignacion:
    reporte = repo.bloquear_reporte(db, reporte_id)
    if reporte is None:
        raise NoEncontrado("El reporte no existe", codigo="REPORTE_NO_ENCONTRADO")

    verificar_misma_organizacion(usuario, reporte.organizacion_objetivo_id)

    if repo.obtener_activa(db, usuario.id, reporte_id=reporte.id) is not None:
        raise Conflicto("Ya tienes este reporte asignado", codigo="ASIGNACION_DUPLICADA")

    asignacion = repo.crear(db, voluntario_id=usuario.id, reporte_id=reporte.id)
    db.commit()
    return asignacion


def listar_mias(
    db: Session, usuario: Usuario, pag: Paginacion, *, estado: EstadoAsignacion | None
) -> tuple[list[Asignacion], int]:
    return repo.listar_de_voluntario(db, pag, voluntario_id=usuario.id, estado=estado)


def _sincronizar_solicitud(
    db: Session, usuario: Usuario, solicitud: SolicitudAyuda, nuevo_estado: EstadoAsignacion
) -> None:
    activas = repo.contar_activas_de_solicitud(db, solicitud.id) if nuevo_estado == EstadoAsignacion.CANCELADA else 0
    destino = estado_solicitud_tras_cambio(solicitud.estado, nuevo_estado, activas)
    if destino is not None:
        solicitudes_repo.actualizar_estado(db, solicitud, estado=destino, modificado_por=usuario.id)


def actualizar_estado(
    db: Session, usuario: Usuario, asignacion_id: UUID, datos: AsignacionEstadoIn
) -> Asignacion:
    asignacion = repo.obtener_por_id(db, asignacion_id)
    if asignacion is None:
        raise NoEncontrado("La asignación no existe", codigo="ASIGNACION_NO_ENCONTRADA")
    if asignacion.voluntario_id != usuario.id:
        raise SinPermiso("Esta asignación no es tuya", codigo="ASIGNACION_AJENA")

    solicitud = None
    if asignacion.solicitud_id is not None:
        solicitud = repo.bloquear_solicitud(db, asignacion.solicitud_id)
        db.refresh(asignacion)  

    if asignacion.estado_asignacion != EstadoAsignacion.ACTIVA:
        raise Conflicto("La asignación ya está cerrada", codigo="TRANSICION_NO_PERMITIDA")

    asignacion = repo.actualizar_estado(db, asignacion, estado=datos.estado)
    if solicitud is not None:
        _sincronizar_solicitud(db, usuario, solicitud, datos.estado)
    db.commit()
    return asignacion
