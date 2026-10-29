"""Modo sin conexión (B7 ampliado).

Dos entradas, el mismo mensaje firmado (ver offline_schema):
- `POST /offline/sync`: el teléfono, al volver la señal, sube SU cola. Solo mensajes propios.
- `POST /offline/relevo`: un teléfono con internet sube mensajes de OTRAS personas que le
  llegaron por Bluetooth. Se aceptan si la firma con la llave del autor es válida.

En los dos: se rechaza lo vencido (más de 24 h), lo que dio más de 8 saltos y lo que no tiene
firma válida; lo repetido (mismo `uuid_origen`, p. ej. llegó por dos teléfonos) se cuenta como
duplicado. Lo aceptado se guarda y el job `procesar_lote_offline` lo convierte en lo real:
- `sos` / `necesito_ayuda`: un SOS (origen `mesh` si llegó por relevo), con su SMS a los contactos.
- `a_salvo`: cierra el "¿Estás bien?" pendiente.
- `sin_respuesta`: el teléfono vio vencer el "¿Estás bien?" sin red: se avisa a los contactos.
- `reporte`: un reporte de incidente (sin fotos) a nombre del autor, que sigue el flujo normal.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.integrations.twilio_client import ErrorSMS, enviar_sms
from app.jobs import encolar as cola
from app.models.cola_alerta_offline import ColaAlertaOffline
from app.models.enums import EstadoCheckIn, EstadoUsuario, MetodoEnvio, OrigenSolicitud
from app.models.usuario import Usuario
from app.repositories import (
    check_ins_repository,
    contactos_emergencia_repository,
    usuarios_repository,
)
from app.repositories import cola_alertas_offline_repository as repo
from app.schemas.offline_schema import (
    MAXIMO_SALTOS,
    LoteOfflineIn,
    LoteOfflineOut,
    MensajeOffline,
    RechazoOut,
    texto_a_firmar,
)
from app.schemas.reportes_schema import ReporteIn
from app.schemas.solicitudes_ayuda_schema import LatLng, SolicitudSOSIn
from app.services import reportes_service, solicitudes_ayuda_service
from app.utils.geo import latlng_desde_punto, punto_desde_latlng

VIGENCIA = timedelta(hours=24)
# Relojes de teléfono adelantados: se tolera un poco de futuro
TOLERANCIA_FUTURO = timedelta(minutes=5)


def llave(db: Session, usuario: Usuario) -> str:
    """La llave HMAC del usuario; se crea la primera vez que la pide."""
    if usuario.llave_offline is None:
        usuarios_repository.actualizar(db, usuario, llave_offline=secrets.token_hex(32))
        db.commit()
    return usuario.llave_offline


def firma(llave_hex: str, mensaje: MensajeOffline) -> str:
    texto = texto_a_firmar(
        mensaje.uuid_origen,
        mensaje.usuario_id,
        mensaje.tipo,
        mensaje.lat,
        mensaje.lng,
        mensaje.generado_en,
        mensaje.reporte,
    )
    return hmac.new(llave_hex.encode(), texto.encode(), hashlib.sha256).hexdigest()


def _motivo_rechazo(db: Session, subidor: Usuario, mensaje: MensajeOffline, relevo: bool) -> str | None:
    if not relevo and mensaje.usuario_id != subidor.id:
        return "NO_ES_TUYO"
    if mensaje.saltos > MAXIMO_SALTOS:
        return "DEMASIADOS_SALTOS"
    try:
        generado = mensaje.generado()
    except ValueError:
        return "FECHA_INVALIDA"
    if generado.tzinfo is None:
        return "FECHA_INVALIDA"
    ahora = datetime.now(UTC)
    if generado < ahora - VIGENCIA or generado > ahora + TOLERANCIA_FUTURO:
        return "MENSAJE_VENCIDO"
    autor = usuarios_repository.obtener_por_id(db, mensaje.usuario_id)
    if autor is None or autor.estado != EstadoUsuario.ACTIVO or autor.llave_offline is None:
        return "USUARIO_DESCONOCIDO"
    if not hmac.compare_digest(firma(autor.llave_offline, mensaje), mensaje.firma.lower()):
        return "FIRMA_INVALIDA"
    return None


def recibir(db: Session, subidor: Usuario, lote: LoteOfflineIn, *, relevo: bool) -> LoteOfflineOut:
    aceptados: list[UUID] = []
    duplicados = 0
    rechazados: list[RechazoOut] = []
    for mensaje in lote.mensajes:
        motivo = _motivo_rechazo(db, subidor, mensaje, relevo)
        if motivo is not None:
            rechazados.append(RechazoOut(uuid_origen=mensaje.uuid_origen, motivo=motivo))
            continue
        metodo = MetodoEnvio.MESH if relevo and mensaje.saltos > 0 else MetodoEnvio.LOCAL
        nuevo_id = repo.guardar_si_es_nuevo(
            db,
            uuid_origen=mensaje.uuid_origen,
            usuario_id=mensaje.usuario_id,
            tipo=mensaje.tipo,
            payload=mensaje.model_dump(mode="json", exclude={"firma"}),
            lat=mensaje.lat,
            lng=mensaje.lng,
            metodo_envio=metodo,
            generado_en=mensaje.generado(),
            subido_por=subidor.id,
            saltos=mensaje.saltos,
        )
        if nuevo_id is None:
            duplicados += 1
        else:
            aceptados.append(nuevo_id)
    db.commit()
    if aceptados:
        # Import aquí: el job importa este service
        from app.jobs.eventos.procesar_lote_offline import procesar_lote_offline

        cola.encolar(procesar_lote_offline, [str(i) for i in aceptados])
    return LoteOfflineOut(aceptados=len(aceptados), duplicados=duplicados, rechazados=rechazados)


def _avisar_contactos(db: Session, autor: Usuario, mensaje: ColaAlertaOffline) -> int:
    posicion = latlng_desde_punto(mensaje.ubicacion)
    texto = (
        f"RESCATE360: {autor.nombre} no respondió si está bien y no tiene conexión. Última ubicación: "
        f"https://maps.google.com/?q={posicion['lat']:.5f},{posicion['lng']:.5f} Si no logras comunicarte, llama al 123."
    )
    enviados = 0
    for contacto in contactos_emergencia_repository.listar_de_usuario(db, autor.id):
        try:
            enviar_sms(contacto.telefono, texto)
            enviados += 1
        except ErrorSMS:
            pass
    return enviados


def procesar(db: Session, mensaje: ColaAlertaOffline) -> str:
    """Convierte un mensaje guardado en lo real. Devuelve el resultado que queda registrado."""
    autor = usuarios_repository.obtener_por_id(db, mensaje.usuario_id)
    if autor is None:
        return "usuario_desconocido"
    pendiente = check_ins_repository.pendiente_de(db, autor.id)
    ahora = datetime.now(UTC)

    if mensaje.tipo in ("sos", "necesito_ayuda"):
        posicion = latlng_desde_punto(mensaje.ubicacion)
        origen = OrigenSolicitud.MESH if mensaje.metodo_envio == MetodoEnvio.MESH else OrigenSolicitud.SOS
        # crear_sos hace commit y encola la clasificación y el SMS a los contactos
        solicitud = solicitudes_ayuda_service.crear_sos(db, autor, SolicitudSOSIn(ubicacion=LatLng(**posicion)), origen)
        if pendiente is not None:
            check_ins_repository.actualizar(
                db,
                pendiente,
                estado=EstadoCheckIn.NECESITO_AYUDA,
                respondido_en=ahora,
                ultima_ubicacion=punto_desde_latlng(posicion["lat"], posicion["lng"]),
                solicitud_id=solicitud.id,
            )
        return "sos_creado"

    if mensaje.tipo == "reporte":
        datos = mensaje.payload["reporte"]
        try:
            entrada = ReporteIn(
                tipo=datos["tipo"],
                descripcion=datos["descripcion"],
                direccion=datos.get("direccion"),
                **latlng_desde_punto(mensaje.ubicacion),
            )
        except ValidationError:
            return "reporte_invalido"
        # crear hace commit y encola la clasificación con IA, igual que un reporte con internet
        reportes_service.crear(db, autor, entrada, [])
        return "reporte_creado"

    if mensaje.tipo == "a_salvo":
        if pendiente is None:
            return "sin_check_in"
        check_ins_repository.actualizar(db, pendiente, estado=EstadoCheckIn.A_SALVO, respondido_en=ahora)
        return "check_in_a_salvo"

    # sin_respuesta: el teléfono vio vencer el "¿Estás bien?" sin red
    if pendiente is not None:
        check_ins_repository.actualizar(
            db, pendiente, estado=EstadoCheckIn.SIN_RESPUESTA, ultima_ubicacion=mensaje.ubicacion
        )
    _avisar_contactos(db, autor, mensaje)
    return "contactos_avisados"


def procesar_ids(db: Session, ids: list[UUID]) -> dict[str, str]:
    resultados = {}
    for mensaje in repo.pendientes_bloqueados(db, ids):
        resultado = procesar(db, mensaje)
        repo.marcar_procesado(db, mensaje, resultado)
        db.commit()
        resultados[str(mensaje.uuid_origen)] = resultado
    return resultados
