from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import Conflicto, NoEncontrado, SinPermiso
from app.jobs import encolar as cola
from app.jobs.eventos.clasificar_prioridad_ia import clasificar_prioridad_ia
from app.jobs.eventos.enviar_sms_respaldo import enviar_sms_respaldo
from app.middlewares.role_middleware import alcance_organizacion, solo_propio, verificar_misma_organizacion
from app.models.enums import EstadoSolicitud, OrigenSolicitud, PrioridadSolicitud, RolUsuario, TipoSolicitud
from app.models.solicitud_ayuda import SolicitudAyuda
from app.models.usuario import Usuario
from app.repositories import asignaciones_repository, organizaciones_repository
from app.repositories import solicitudes_ayuda_repository as repo
from app.schemas.solicitudes_ayuda_schema import (
    SolicitudAyudaIn,
    SolicitudAyudaOut,
    SolicitudEstadoIn,
    SolicitudOrganizacionIn,
    SolicitudPrioridadIn,
    SolicitudSOSIn,
)
from app.utils.geo import punto_desde_latlng
from app.utils.paginacion import Paginacion

DESCRIPCION_SOS = "Solicitud de emergencia (SOS)"
ESTADOS_ABIERTOS = (EstadoSolicitud.PENDIENTE, EstadoSolicitud.EN_PROCESO)


def organizacion_efectiva(solicitud: SolicitudAyuda) -> UUID | None:
    if solicitud.organizacion_manual_id is not None:
        return solicitud.organizacion_manual_id
    return solicitud.organizacion_objetivo_id


def verificar_acceso(usuario: Usuario, solicitud: SolicitudAyuda) -> None:
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


def a_salida(usuario: Usuario, solicitud: SolicitudAyuda) -> SolicitudAyudaOut:
    """La solicitud como la ve este usuario: el ciudadano no recibe quién la atiende."""
    salida = SolicitudAyudaOut.model_validate(solicitud)
    if usuario.rol == RolUsuario.CIUDADANO:
        salida.atencion = None
    return salida


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
    # Después del commit, para que el worker encuentre la fila
    cola.encolar(clasificar_prioridad_ia, str(solicitud.id))
    return solicitud


def crear_sos(
    db: Session, usuario: Usuario, datos: SolicitudSOSIn, origen: OrigenSolicitud = OrigenSolicitud.SOS
) -> SolicitudAyuda:
    """El SOS no espera a la IA: nace crítico y de tipo rescate. `origen=mesh` si llegó por relevo Bluetooth."""
    solicitud = repo.crear(
        db,
        usuario_id=usuario.id,
        descripcion=DESCRIPCION_SOS,
        tipo=TipoSolicitud.RESCATE,
        ubicacion=punto_desde_latlng(datos.ubicacion.lat, datos.ubicacion.lng),
        origen=origen,
        prioridad_ia=PrioridadSolicitud.CRITICA,
    )
    db.commit()
    # La prioridad ya es crítica; el job solo la enruta a una organización de rescate
    cola.encolar(clasificar_prioridad_ia, str(solicitud.id))
    # SMS a los contactos de emergencia: llega aunque no tengan la app ni internet
    cola.encolar(enviar_sms_respaldo, str(solicitud.id))
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


def asignar_organizacion(
    db: Session, usuario: Usuario, solicitud_id: UUID, datos: SolicitudOrganizacionIn
) -> SolicitudAyuda:
    """Solo super_admin (se exige en la ruta). Mientras no haya IA, así llega el caso a una organización."""
    solicitud = asignaciones_repository.bloquear_solicitud(db, solicitud_id)
    if solicitud is None:
        raise NoEncontrado("La solicitud no existe", codigo="SOLICITUD_NO_ENCONTRADA")
    organizacion = organizaciones_repository.obtener_por_id(db, datos.organizacion_id)
    if organizacion is None:
        raise NoEncontrado("La organización no existe", codigo="ORGANIZACION_NO_ENCONTRADA")
    if not organizacion.activa:
        raise Conflicto("La organización está desactivada", codigo="ORGANIZACION_INACTIVA")
    if solicitud.estado not in ESTADOS_ABIERTOS:
        raise Conflicto("La solicitud ya está cerrada", codigo="SOLICITUD_CERRADA")
    # Los voluntarios que la tienen son de la organización anterior: primero deben soltarla
    if asignaciones_repository.contar_activas_de_solicitud(db, solicitud.id) > 0:
        raise Conflicto(
            "La solicitud tiene voluntarios asignados; deben cancelar su asignación antes de moverla",
            codigo="SOLICITUD_CON_ASIGNACIONES",
        )
    solicitud = repo.actualizar_organizacion(
        db, solicitud, organizacion_id=organizacion.id, modificado_por=usuario.id
    )
    db.commit()
    return solicitud


def cancelar_propia(db: Session, usuario: Usuario, solicitud_id: UUID) -> SolicitudAyuda:
    """El dueño cancela su solicitud (p. ej. ya no necesita ayuda). Las asignaciones activas se cancelan."""
    solicitud = asignaciones_repository.bloquear_solicitud(db, solicitud_id)
    if solicitud is None:
        raise NoEncontrado("La solicitud no existe", codigo="SOLICITUD_NO_ENCONTRADA")
    if solicitud.usuario_id != usuario.id:
        raise SinPermiso("Solo quien creó la solicitud puede cancelarla", codigo="SOLICITUD_FUERA_DE_ALCANCE")
    if solicitud.estado not in ESTADOS_ABIERTOS:
        raise Conflicto("La solicitud ya está cerrada", codigo="SOLICITUD_CERRADA")
    asignaciones_repository.cancelar_activas_de_solicitud(db, solicitud.id)
    solicitud = repo.actualizar_estado(db, solicitud, estado=EstadoSolicitud.CANCELADA, modificado_por=usuario.id)
    db.commit()
    return solicitud
