from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.contacto_emergencia import ContactoEmergencia


def listar_de_usuario(db: Session, usuario_id: UUID) -> list[ContactoEmergencia]:
    consulta = (
        select(ContactoEmergencia)
        .where(ContactoEmergencia.usuario_id == usuario_id)
        .order_by(ContactoEmergencia.creado_en, ContactoEmergencia.id)
    )
    return list(db.scalars(consulta))


def contar_de_usuario(db: Session, usuario_id: UUID) -> int:
    consulta = select(func.count()).select_from(ContactoEmergencia).where(ContactoEmergencia.usuario_id == usuario_id)
    return db.scalar(consulta) or 0


def existe_telefono(db: Session, usuario_id: UUID, telefono: str, excluir_id: UUID | None = None) -> bool:
    filtros = [ContactoEmergencia.usuario_id == usuario_id, ContactoEmergencia.telefono == telefono]
    if excluir_id is not None:
        filtros.append(ContactoEmergencia.id != excluir_id)
    return db.scalar(select(func.count()).select_from(ContactoEmergencia).where(*filtros)) > 0


def obtener_de_usuario(db: Session, usuario_id: UUID, contacto_id: UUID) -> ContactoEmergencia | None:
    consulta = select(ContactoEmergencia).where(
        ContactoEmergencia.id == contacto_id, ContactoEmergencia.usuario_id == usuario_id
    )
    return db.scalar(consulta)


def crear(db: Session, **campos) -> ContactoEmergencia:
    # Hora real y no now() de Postgres (inicio de la transacción), para que el orden sea el de creación
    contacto = ContactoEmergencia(**campos, creado_en=datetime.now(UTC))
    db.add(contacto)
    db.flush()
    db.refresh(contacto)
    return contacto


def actualizar(db: Session, contacto: ContactoEmergencia, **campos) -> ContactoEmergencia:
    for campo, valor in campos.items():
        setattr(contacto, campo, valor)
    db.flush()
    db.refresh(contacto)
    return contacto


def eliminar(db: Session, contacto: ContactoEmergencia) -> None:
    db.delete(contacto)
    db.flush()


def eliminar_de_usuario(db: Session, usuario_id: UUID) -> None:
    db.execute(delete(ContactoEmergencia).where(ContactoEmergencia.usuario_id == usuario_id))
