from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.excepciones import Conflicto, NoAutenticado
from app.core.security import (
    TOKEN_REFRESH,
    crear_access_token,
    crear_refresh_token,
    decodificar_token,
    hash_password,
    verify_password,
)
from app.middlewares.audit_middleware import fijar_actor
from app.middlewares.auth_middleware import verificar_estado
from app.models.enums import RolUsuario, TipoConsentimiento
from app.models.usuario import Usuario
from app.repositories import consentimientos_repository, usuarios_repository
from app.schemas.auth_schema import LoginIn, RegistroIn, SesionOut
from app.schemas.usuarios_schema import UsuarioOut

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
