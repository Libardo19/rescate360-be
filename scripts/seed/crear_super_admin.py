"""Crea el super admin inicial. El super admin NUNCA se crea por registro público.

Toma los datos del .env (SUPER_ADMIN_NOMBRE, SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD):

    docker compose exec api python -m scripts.seed.crear_super_admin

Es idempotente: si ya existe un super admin con ese correo, no hace nada.
"""

import sys

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import BCRYPT_MAX_BYTES, hash_password
from app.models.enums import EstadoUsuario, RolUsuario
from app.models.usuario import Usuario
from app.repositories import usuarios_repository


class ErrorSeed(Exception):
    pass


def crear_super_admin(db: Session, *, nombre: str, email: str, password: str) -> tuple[Usuario, bool]:
    """Devuelve (usuario, creado). `creado` es False si ya existía."""
    email = email.strip().lower()
    if not email or not password:
        raise ErrorSeed("Faltan SUPER_ADMIN_EMAIL o SUPER_ADMIN_PASSWORD en el .env")
    if len(password) < 8 or len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ErrorSeed(f"SUPER_ADMIN_PASSWORD debe tener entre 8 caracteres y {BCRYPT_MAX_BYTES} bytes")

    existente = usuarios_repository.obtener_por_email(db, email)
    if existente is not None:
        if existente.rol != RolUsuario.SUPER_ADMIN:
            raise ErrorSeed(f"{email} ya existe con rol {existente.rol.value}; usa otro correo")
        return existente, False

    usuario = usuarios_repository.crear(
        db,
        nombre=" ".join(nombre.split()) or "Super Admin",
        email=email,
        password_hash=hash_password(password),
        rol=RolUsuario.SUPER_ADMIN,
        estado=EstadoUsuario.ACTIVO,
        organizacion_id=None,
    )
    db.commit()
    db.refresh(usuario)
    return usuario, True


def main() -> int:
    settings = get_settings()
    with SessionLocal() as db:
        try:
            usuario, creado = crear_super_admin(
                db,
                nombre=settings.super_admin_nombre,
                email=settings.super_admin_email,
                password=settings.super_admin_password,
            )
        except ErrorSeed as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
    print(f"{'Creado' if creado else 'Ya existía'}: {usuario.codigo} {usuario.email} (super_admin)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
