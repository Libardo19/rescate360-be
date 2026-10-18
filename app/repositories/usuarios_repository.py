from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.usuario import Usuario


def obtener_por_id(db: Session, usuario_id: UUID) -> Usuario | None:
    return db.get(Usuario, usuario_id)


def obtener_por_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(func.lower(Usuario.email) == email.lower()))


def crear(db: Session, **campos) -> Usuario:
    usuario = Usuario(**campos)
    db.add(usuario)
    db.flush()  # asigna el id generado por la BD
    return usuario


def registrar_acceso(db: Session, usuario: Usuario) -> None:
    usuario.ultimo_acceso = datetime.now(UTC)
    db.flush()
