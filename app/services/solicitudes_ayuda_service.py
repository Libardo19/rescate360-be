from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import NoEncontrado, SinPermiso
from app.middlewares.role_middleware import alcance_organizacion, solo_propio, verificar_misma_organizacion
from app.models.enums import OrigenSolicitud, PrioridadSolicitud, TipoSolicitud
from app.models.solicitud_ayuda import SolicitudAyuda
from app.models.usuario import Usuario
from app.repositories import solicitudes_ayuda_repository as repo
from app.schemas.solicitudes_ayuda_schema import (
    SolicitudAyudaIn,
    SolicitudEstadoIn,
    SolicitudPrioridadIn,
    SolicitudSOSIn,
)
from app.utils.geo import punto_desde_latlng
from app.utils.paginacion import Paginacion

DESCRIPCION_SOS = "Solicitud de emergencia (SOS)"


def organizacion_efectiva(solicitud: SolicitudAyuda) -> UUID | None:
    """Organización dueña del caso: la asignada a mano prevalece sobre la sugerida por la IA.

    Hoy nadie llena ninguna de las dos, así que el caso solo lo ve el super_admin. Cuando exista el
    enrutamiento solo cambia quién llena organizacion_objetivo_id; esta función y el resto no cambian.
    """
    if solicitud.organizacion_manual_id is not None:
        return solicitud.organizacion_manual_id
    return solicitud.organizacion_objetivo_id


def verificar_acceso(usuario: Usuario, solicitud: SolicitudAyuda) -> None:
    """Matriz de permisos: ciudadano solo lo propio; voluntario y administrador, su organización; super_admin, todo."""
    dueno_id = solo_propio(usuario)
    if dueno_id is not None:  # es ciudadano
        if solicitud.usuario_id != dueno_id:
            raise SinPermiso("No tienes acceso a esta solicitud", codigo="SOLICITUD_FUERA_DE_ALCANCE")
        return
    verificar_misma_organizacion(usuario, organizacion_efectiva(solicitud))


def obtener_solicitud(db: Session, usuario: Usuario, solicitud_id: UUID) -> SolicitudAyuda:
    solicitud = repo.obtener_por_id(db, solicitud_id)
    if solicitud is None:
        raise NoEncontrado("La solicitud no existe", codigo="SOLICITUD_NO_ENCONTRADA")
    verificar_acceso(usuario, solicitud)
    return solicitud


def crear_solicitud(db: Session, usuario: Usuario, datos: SolicitudAyudaIn) -> SolicitudAyuda:
    solicitud = repo.crear(
        db,
        usuario_id=usuario.id,
        descripcion=datos.descripcion,
        direccion=datos.direccion,
        tipo=datos.tipo,
        ubicacion=punto_desde_latlng(datos.ubicacion.lat, datos.ubicacion.lng),
        origen=OrigenSolicitud.MANUAL,
        prioridad_ia=PrioridadSolicitud.PENDIENTE,
    )
    db.commit()
    # TODO (IA, B2 del plan): aquí, DESPUÉS del commit para que el job vea la fila:
    #     clasificar_prioridad_ia.delay(str(solicitud.id))
    return solicitud


def crear_sos(db: Session, usuario: Usuario, datos: SolicitudSOSIn) -> SolicitudAyuda:
    """El SOS no espera a la IA: nace crítico y de tipo rescate."""
    solicitud = repo.crear(
        db,
        usuario_id=usuario.id,
        descripcion=DESCRIPCION_SOS,
        tipo=TipoSolicitud.RESCATE,
        ubicacion=punto_desde_latlng(datos.ubicacion.lat, datos.ubicacion.lng),
        origen=OrigenSolicitud.SOS,
        prioridad_ia=PrioridadSolicitud.CRITICA,
    )
    db.commit()
    # TODO (B3): enviar_sms_respaldo.delay(str(solicitud.id)) -> SMS a los contactos de emergencia
    return solicitud


def listar_solicitudes(
    db: Session,
    usuario: Usuario,
    pag: Paginacion,
    *,
    estado,
    tipo,
    prioridad,
) -> tuple[list[SolicitudAyuda], int]:
    dueno_id = solo_propio(usuario)
    if dueno_id is not None:  # ciudadano: alcance_organizacion lanzaría SinPermiso para él
        filtros = {"usuario_id": dueno_id}
    else:  # voluntario/administrador -> su organización; super_admin -> None (sin filtro)
        filtros = {"organizacion_id": alcance_organizacion(usuario)}
    return repo.listar(db, pag, estado=estado, tipo=tipo, prioridad=prioridad, **filtros)


def actualizar_prioridad(
    db: Session, usuario: Usuario, solicitud_id: UUID, datos: SolicitudPrioridadIn
) -> SolicitudAyuda:
    """Solo administrador y super_admin (se exige en la ruta)."""
    solicitud = obtener_solicitud(db, usuario, solicitud_id)
    solicitud = repo.actualizar_prioridad(
        db, solicitud, prioridad_manual=datos.prioridad_manual, modificado_por=usuario.id
    )
    db.commit()
    return solicitud


def actualizar_estado(db: Session, usuario: Usuario, solicitud_id: UUID, datos: SolicitudEstadoIn) -> SolicitudAyuda:
    """Solo administrador y super_admin (se exige en la ruta). Sin reglas de transición: el plan no las define."""
    solicitud = obtener_solicitud(db, usuario, solicitud_id)
    solicitud = repo.actualizar_estado(db, solicitud, estado=datos.estado, modificado_por=usuario.id)
    db.commit()
    return solicitud
