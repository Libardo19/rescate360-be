import hmac
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.excepciones import Conflicto, DatosInvalidos, NoAutenticado
from app.core.security import (
    TOKEN_REFRESH,
    crear_access_token,
    crear_refresh_token,
    decodificar_token,
    generar_codigo_activacion,
    hash_codigo,
    hash_password,
    verify_password,
)
from app.integrations import correo_client, twilio_client
from app.middlewares.audit_middleware import fijar_actor
from app.middlewares.auth_middleware import verificar_estado
from app.models.enums import EstadoUsuario, RolUsuario, TipoConsentimiento
from app.models.usuario import Usuario
from app.repositories import consentimientos_repository, usuarios_repository
from app.schemas.auth_schema import ActivarIn, LoginIn, RecuperarIn, RegistroIn, RestablecerIn, SesionOut
from app.schemas.usuarios_schema import UsuarioOut

logger = logging.getLogger(__name__)

# Respuesta única de POST /auth/recuperar, exista o no la cuenta
MENSAJE_RECUPERACION = "Si la cuenta existe y tiene ese medio registrado, te enviamos un código para cambiar la contraseña"

# Hash fijo para comparar cuando el correo no existe: así el login tarda lo mismo
# con un correo inexistente que con una contraseña incorrecta.
_HASH_SENUELO = hash_password("contraseña-que-nadie-usa")


def _sesion(usuario: Usuario) -> SesionOut:
    return SesionOut(
        access_token=crear_access_token(usuario),
        refresh_token=crear_refresh_token(usuario),
        usuario=UsuarioOut.model_validate(usuario),
    )


def registrar(db: Session, datos: RegistroIn, ip: str | None) -> SesionOut:
    """Autorregistro público: siempre crea un ciudadano (nunca otro rol)."""
    if usuarios_repository.obtener_por_email(db, datos.email):
        raise Conflicto("Ya existe una cuenta con ese correo", codigo="EMAIL_YA_REGISTRADO")

    try:
        usuario = usuarios_repository.crear(
            db,
            nombre=datos.nombre,
            email=datos.email,
            telefono=datos.telefono,
            password_hash=hash_password(datos.password),
            rol=RolUsuario.CIUDADANO,
        )
    except IntegrityError:  # dos registros simultáneos con el mismo correo
        db.rollback()
        raise Conflicto("Ya existe una cuenta con ese correo", codigo="EMAIL_YA_REGISTRADO") from None

    # Desde aquí el actor de auditoría es el propio usuario
    fijar_actor(db, usuario.id)
    consentimientos_repository.registrar(
        db,
        usuario_id=usuario.id,
        tipo=TipoConsentimiento.TRATAMIENTO_DATOS,
        aceptado=True,
        version_politica=get_settings().version_politica_datos,
        ip=ip,
    )
    db.commit()
    return _sesion(usuario)


def login(db: Session, datos: LoginIn) -> SesionOut:
    usuario = usuarios_repository.obtener_por_email(db, datos.email)
    hash_a_comparar = usuario.password_hash if usuario else _HASH_SENUELO
    if not verify_password(datos.password, hash_a_comparar) or usuario is None:
        raise NoAutenticado("Correo o contraseña incorrectos", codigo="CREDENCIALES_INVALIDAS")
    verificar_estado(usuario)

    fijar_actor(db, usuario.id)
    usuarios_repository.registrar_acceso(db, usuario)
    db.commit()
    return _sesion(usuario)


def activar(db: Session, datos: ActivarIn, ip: str | None) -> SesionOut:
    """Canje del código de invitación: la persona pone su contraseña y la cuenta queda activa.

    Correo inexistente, código errado, vencido o cuenta que no está en espera responden
    igual, para no revelar qué correos tienen invitación.
    """
    usuario = usuarios_repository.obtener_por_email(db, datos.email)
    valido = (
        usuario is not None
        and usuario.estado == EstadoUsuario.EN_ESPERA
        and usuario.codigo_activacion_hash is not None
        and usuario.codigo_activacion_vence is not None
        and usuario.codigo_activacion_vence > datetime.now(UTC)
        and hmac.compare_digest(usuario.codigo_activacion_hash, hash_codigo(datos.codigo))
    )
    if not valido:
        raise DatosInvalidos("El código no es válido o ya venció", codigo="CODIGO_ACTIVACION_INVALIDO")

    fijar_actor(db, usuario.id)
    usuarios_repository.actualizar(
        db,
        usuario,
        password_hash=hash_password(datos.password),
        estado=EstadoUsuario.ACTIVO,
        codigo_activacion_hash=None,
        codigo_activacion_vence=None,
        ultimo_acceso=datetime.now(UTC),
    )
    verificar_estado(usuario)  # p. ej. su organización fue desactivada mientras tanto: no se guarda nada
    consentimientos_repository.registrar(
        db,
        usuario_id=usuario.id,
        tipo=TipoConsentimiento.TRATAMIENTO_DATOS,
        aceptado=True,
        version_politica=get_settings().version_politica_datos,
        ip=ip,
    )
    db.commit()
    return _sesion(usuario)


def recuperar(db: Session, datos: RecuperarIn) -> None:
    """Genera un código de un solo uso y lo envía por el canal elegido.

    Correo inexistente, cuenta no activa o canal sin dato (p. ej. SMS sin teléfono) no hacen
    nada y responden igual, para no revelar qué correos están registrados.
    """
    usuario = usuarios_repository.obtener_por_email(db, datos.email)
    if usuario is None or usuario.estado != EstadoUsuario.ACTIVO:
        return
    if datos.canal == "sms" and not usuario.telefono:
        return

    minutos = get_settings().recuperacion_minutos
    codigo = generar_codigo_activacion()
    fijar_actor(db, usuario.id)
    usuarios_repository.actualizar(
        db,
        usuario,
        codigo_recuperacion_hash=hash_codigo(codigo),
        codigo_recuperacion_vence=datetime.now(UTC) + timedelta(minutes=minutos),
    )
    db.commit()

    texto = (
        f"RESCATE360: tu código para cambiar la contraseña es {codigo}. Vence en {minutos} minutos. "
        "Si no lo pediste, ignora este mensaje."
    )
    # Si el envío falla, el usuario puede pedir otro código; la respuesta no cambia
    try:
        if datos.canal == "sms":
            twilio_client.enviar_sms(usuario.telefono, texto)
        else:
            correo_client.enviar_correo(usuario.email, "Código para cambiar tu contraseña", texto)
    except (twilio_client.ErrorSMS, correo_client.ErrorCorreo):
        logger.exception("No se pudo enviar el código de recuperación por %s", datos.canal)


def restablecer(db: Session, datos: RestablecerIn) -> SesionOut:
    """Canje del código de recuperación: pone la contraseña nueva y abre sesión."""
    usuario = usuarios_repository.obtener_por_email(db, datos.email)
    valido = (
        usuario is not None
        and usuario.estado == EstadoUsuario.ACTIVO
        and usuario.codigo_recuperacion_hash is not None
        and usuario.codigo_recuperacion_vence is not None
        and usuario.codigo_recuperacion_vence > datetime.now(UTC)
        and hmac.compare_digest(usuario.codigo_recuperacion_hash, hash_codigo(datos.codigo))
    )
    if not valido:
        raise DatosInvalidos("El código no es válido o ya venció", codigo="CODIGO_RECUPERACION_INVALIDO")
    verificar_estado(usuario)

    fijar_actor(db, usuario.id)
    usuarios_repository.actualizar(
        db,
        usuario,
        password_hash=hash_password(datos.password),
        codigo_recuperacion_hash=None,
        codigo_recuperacion_vence=None,
        ultimo_acceso=datetime.now(UTC),
    )
    db.commit()
    return _sesion(usuario)


def refrescar(db: Session, refresh_token: str) -> SesionOut:
    payload = decodificar_token(refresh_token, TOKEN_REFRESH)
    try:
        usuario = usuarios_repository.obtener_por_id(db, UUID(payload["sub"]))
    except ValueError:
        usuario = None
    if usuario is None:
        raise NoAutenticado("Token inválido", codigo="TOKEN_INVALIDO")
    verificar_estado(usuario)
    return _sesion(usuario)
