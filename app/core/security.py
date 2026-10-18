"""Contraseñas (bcrypt) y tokens de sesión (JWT)."""

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.excepciones import NoAutenticado

# bcrypt solo usa los primeros 72 bytes y la versión 5 rechaza contraseñas más largas.
BCRYPT_MAX_BYTES = 72

TOKEN_ACCESS = "access"
TOKEN_REFRESH = "refresh"


def hash_password(password: str) -> str:
    datos = password.encode("utf-8")
    if len(datos) > BCRYPT_MAX_BYTES:
        raise ValueError(f"La contraseña no puede superar {BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(datos, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    datos = password.encode("utf-8")
    if len(datos) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(datos, password_hash.encode("utf-8"))
    except ValueError:  # hash con formato inválido
        return False


def _crear_token(usuario, tipo: str, duracion: timedelta) -> str:
    settings = get_settings()
    ahora = datetime.now(UTC)
    payload = {
        "sub": str(usuario.id),
        "rol": usuario.rol.value,
        "organizacion_id": str(usuario.organizacion_id) if usuario.organizacion_id else None,
        "tipo": tipo,
        "iat": ahora,
        "exp": ahora + duracion,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def crear_access_token(usuario) -> str:
    minutos = get_settings().jwt_access_expires_min
    return _crear_token(usuario, TOKEN_ACCESS, timedelta(minutes=minutos))


def crear_refresh_token(usuario) -> str:
    dias = get_settings().jwt_refresh_expires_days
    return _crear_token(usuario, TOKEN_REFRESH, timedelta(days=dias))


def decodificar_token(token: str, tipo_esperado: str) -> dict:
    """Valida firma, expiración y tipo. Lanza NoAutenticado si algo falla."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "tipo"]},
        )
    except jwt.ExpiredSignatureError:
        raise NoAutenticado("La sesión expiró, vuelve a iniciar sesión", codigo="TOKEN_EXPIRADO") from None
    except jwt.InvalidTokenError:
        raise NoAutenticado("Token inválido", codigo="TOKEN_INVALIDO") from None

    if payload["tipo"] != tipo_esperado:
        raise NoAutenticado("Token inválido", codigo="TOKEN_INVALIDO")
    return payload
