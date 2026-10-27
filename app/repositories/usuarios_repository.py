from datetime import UTC, datetime
from uuid import UUID

from geoalchemy2.elements import WKTElement
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


def actualizar_ubicacion(db: Session, usuario: Usuario, ubicacion: WKTElement) -> Usuario:
    usuario.ubicacion_actual = ubicacion
    usuario.ubicacion_actualizada_en = datetime.now(UTC)
    db.flush()
    db.refresh(usuario)  # ubicacion_actual vuelve como WKBElement, igual que al leerla
    return usuario


def borrar_ubicacion(db: Session, usuario: Usuario) -> None:
    usuario.ubicacion_actual = None
    usuario.ubicacion_actualizada_en = None
    db.flush()
