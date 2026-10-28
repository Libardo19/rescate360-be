"""Usuario autenticado de la petición.

    from app.middlewares.auth_middleware import get_current_user

    def mi_endpoint(usuario: Usuario = Depends(get_current_user)): ...

Devuelve el objeto ORM `Usuario` (con `usuario.rol` como `RolUsuario`) y deja
fijado el actor de auditoría en la sesión de la petición.
"""

from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.excepciones import NoAutenticado, SinPermiso
from app.core.security import TOKEN_ACCESS, decodificar_token
from app.middlewares.audit_middleware import fijar_actor
from app.models.enums import EstadoUsuario
from app.models.usuario import Usuario
from app.repositories import usuarios_repository

_bearer = HTTPBearer(auto_error=False, description="Token de acceso: `Authorization: Bearer <token>`")


def verificar_estado(usuario: Usuario) -> None:
    """Un usuario bloqueado, pendiente de activación o de una organización desactivada no puede operar."""
    if usuario.estado == EstadoUsuario.BLOQUEADO:
        raise SinPermiso("Tu cuenta está bloqueada", codigo="USUARIO_BLOQUEADO")
    if usuario.estado == EstadoUsuario.EN_ESPERA:
        raise SinPermiso("Tu cuenta todavía no ha sido activada", codigo="USUARIO_EN_ESPERA")
    if usuario.organizacion is not None and not usuario.organizacion.activa:
        raise SinPermiso("Tu organización está desactivada", codigo="ORGANIZACION_INACTIVA")


def get_current_user(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    if credenciales is None:
        raise NoAutenticado("Debes iniciar sesión", codigo="TOKEN_REQUERIDO")

    payload = decodificar_token(credenciales.credentials, TOKEN_ACCESS)
    try:
        usuario_id = UUID(payload["sub"])
    except ValueError:
        raise NoAutenticado("Token invalido", codigo="TOKEN_INVALIDO") from None

    usuario = usuarios_repository.obtener_por_id(db, usuario_id)
    if usuario is None:
        raise NoAutenticado("Token invalido", codigo="TOKEN_INVALIDO")
    verificar_estado(usuario)

    fijar_actor(db, usuario.id)
    return usuario


def get_current_user_optional(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario | None:
    if credenciales is None:
        return None

    try:
        payload = decodificar_token(credenciales.credentials, TOKEN_ACCESS)
        usuario_id = UUID(payload["sub"])
        usuario = usuarios_repository.obtener_por_id(db, usuario_id)
        if usuario is None:
            return None
        try:
            verificar_estado(usuario)
        except Exception:
            return None
        fijar_actor(db, usuario.id)
        return usuario
    except Exception:
        return None

