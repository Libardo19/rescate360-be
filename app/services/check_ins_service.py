"""El "¿Estás bien?" con vencimiento (check-in).

- Lo abre un sismo fuerte para quien esté cerca, o la persona misma ("modo emergencia").
- La app lo consulta con `GET /check-ins/pendiente` al abrir y cada minuto (sin push todavía).
- Responder `a_salvo` lo cierra; `necesito_ayuda` crea un SOS con la ubicación (y el SOS ya
  manda el SMS a los contactos de emergencia).
- Si nadie responde antes de `vence_en`, el job `vencer_check_ins` lo deja `sin_respuesta` y
  avisa por SMS a los contactos con la última ubicación conocida.
- El panel (administrador y super admin) ve el resumen por sismo: a salvo, pidió ayuda o no respondió.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.excepciones import Conflicto, DatosInvalidos, NoEncontrado
from app.models.check_in import CheckIn
from app.models.enums import EstadoCheckIn
from app.models.usuario import Usuario
from app.repositories import check_ins_repository as repo
from app.schemas.sismos_schema import (
    CheckInManualIn,
    CheckInsEventoOut,
    PersonaCheckInOut,
    RespuestaCheckInIn,
    ResumenCheckInsOut,
)
from app.schemas.solicitudes_ayuda_schema import LatLng, SolicitudSOSIn
from app.services import solicitudes_ayuda_service
from app.utils.geo import latlng_desde_punto, punto_desde_latlng


def _vence() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=get_settings().check_in_minutos)


def pendiente(db: Session, usuario: Usuario) -> CheckIn | None:
    return repo.pendiente_de(db, usuario.id)


def activar_modo_emergencia(db: Session, usuario: Usuario, datos: CheckInManualIn) -> CheckIn:
    if repo.pendiente_de(db, usuario.id) is not None:
        raise Conflicto("Ya tienes un \"¿Estás bien?\" pendiente", codigo="CHECK_IN_PENDIENTE")
    ubicacion = datos.ubicacion
    check_in = repo.crear(
        db,
        usuario_id=usuario.id,
        motivo="manual",
        ultima_ubicacion=(
            punto_desde_latlng(ubicacion.lat, ubicacion.lng) if ubicacion is not None else usuario.ubicacion_actual
        ),
        vence_en=_vence(),
    )
    db.commit()
    return check_in


def responder(db: Session, usuario: Usuario, check_in_id: UUID, datos: RespuestaCheckInIn) -> CheckIn:
    check_in = repo.bloquear(db, check_in_id)
    # El de otra persona responde igual que uno inexistente
    if check_in is None or check_in.usuario_id != usuario.id:
        raise NoEncontrado("El \"¿Estás bien?\" no existe", codigo="CHECK_IN_NO_ENCONTRADO")
    if check_in.estado != EstadoCheckIn.PENDIENTE:
        raise Conflicto("Ya se respondió o venció", codigo="CHECK_IN_CERRADO")

    campos: dict = {"estado": EstadoCheckIn(datos.estado), "respondido_en": datetime.now(UTC)}
    if datos.ubicacion is not None:
        campos["ultima_ubicacion"] = punto_desde_latlng(datos.ubicacion.lat, datos.ubicacion.lng)
    check_in = repo.actualizar(db, check_in, **campos)

    if check_in.estado == EstadoCheckIn.NECESITO_AYUDA:
        posicion = latlng_desde_punto(check_in.ultima_ubicacion or usuario.ubicacion_actual)
        if posicion is None:
            db.rollback()
            raise DatosInvalidos("Envía tu ubicación para que llegue la ayuda", codigo="UBICACION_REQUERIDA")
        # crear_sos hace commit y encola la clasificación y el SMS a los contactos
        solicitud = solicitudes_ayuda_service.crear_sos(db, usuario, SolicitudSOSIn(ubicacion=LatLng(**posicion)))
        check_in = repo.actualizar(db, check_in, solicitud_id=solicitud.id)
    db.commit()
    return check_in


def vencer(db: Session) -> list[tuple[CheckIn, Usuario]]:
    """Marca `sin_respuesta` los vencidos y, si se conoce dónde está la persona, sube su SOS
    automático (crítico, con su última ubicación): quien no responde puede estar atrapado o herido.
    Devuelve (check_in, usuario) para avisar a sus contactos (el job manda un solo SMS)."""
    vencidos = repo.vencidos_bloqueados(db)
    resultado = []
    for check_in in vencidos:
        repo.actualizar(db, check_in, estado=EstadoCheckIn.SIN_RESPUESTA)
        resultado.append((check_in, db.get(Usuario, check_in.usuario_id)))
    db.commit()
    for check_in, usuario in resultado:
        _sos_por_falta_de_respuesta(db, check_in, usuario)
    return resultado


def _sos_por_falta_de_respuesta(db: Session, check_in: CheckIn, usuario: Usuario) -> None:
    posicion = latlng_desde_punto(check_in.ultima_ubicacion or usuario.ubicacion_actual)
    if posicion is None:
        return  # sin ubicación no hay a dónde mandar la ayuda: quedan los SMS a los contactos
    solicitud = solicitudes_ayuda_service.crear_sos(
        db,
        usuario,
        SolicitudSOSIn(ubicacion=LatLng(**posicion)),
        descripcion=solicitudes_ayuda_service.DESCRIPCION_SOS_SIN_RESPUESTA,
        avisar_contactos=False,
    )
    campos: dict = {"solicitud_id": solicitud.id}
    if check_in.ultima_ubicacion is None:
        campos["ultima_ubicacion"] = punto_desde_latlng(posicion["lat"], posicion["lng"])
    repo.actualizar(db, check_in, **campos)
    db.commit()


def _persona(check_in: CheckIn, persona: Usuario) -> PersonaCheckInOut:
    return PersonaCheckInOut(
        id=check_in.id,
        motivo=check_in.motivo,
        estado=check_in.estado,
        evento_sismico_id=check_in.evento_sismico_id,
        ultima_ubicacion=check_in.ultima_ubicacion,
        vence_en=check_in.vence_en,
        respondido_en=check_in.respondido_en,
        solicitud_id=check_in.solicitud_id,
        creado_en=check_in.creado_en,
        usuario_id=persona.id,
        nombre=persona.nombre,
        telefono=persona.telefono,
    )


def por_evento(db: Session, evento_sismico_id: UUID | None) -> CheckInsEventoOut:
    """Para el panel (administrador y super admin, se exige en la ruta)."""
    filas = repo.listar_con_usuario(db, evento_sismico_id)
    resumen = ResumenCheckInsOut()
    for check_in, _ in filas:
        setattr(resumen, check_in.estado.value, getattr(resumen, check_in.estado.value) + 1)
    return CheckInsEventoOut(resumen=resumen, personas=[_persona(c, u) for c, u in filas])
