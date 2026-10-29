"""Contactos de emergencia (A6). Cada usuario gestiona solo los suyos, máximo 5.

Al activar el SOS, el job `enviar_sms_respaldo` les manda un SMS con la ubicación.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import Conflicto, NoEncontrado
from app.models.contacto_emergencia import ContactoEmergencia
from app.models.usuario import Usuario
from app.repositories import contactos_emergencia_repository as repo
from app.schemas.contactos_emergencia_schema import MAXIMO_CONTACTOS, ContactoCambiosIn, ContactoIn


def listar(db: Session, usuario: Usuario) -> list[ContactoEmergencia]:
    return repo.listar_de_usuario(db, usuario.id)


def _telefono_libre(db: Session, usuario: Usuario, telefono: str, excluir_id: UUID | None = None) -> None:
    if repo.existe_telefono(db, usuario.id, telefono, excluir_id):
        raise Conflicto("Ya tienes un contacto con ese teléfono", codigo="CONTACTO_DUPLICADO")


def crear(db: Session, usuario: Usuario, datos: ContactoIn) -> ContactoEmergencia:
    if repo.contar_de_usuario(db, usuario.id) >= MAXIMO_CONTACTOS:
        raise Conflicto(
            f"Puedes tener máximo {MAXIMO_CONTACTOS} contactos de emergencia", codigo="MAXIMO_CONTACTOS"
        )
    _telefono_libre(db, usuario, datos.telefono)
    contacto = repo.crear(db, usuario_id=usuario.id, **datos.model_dump())
    db.commit()
    return contacto


def _propio(db: Session, usuario: Usuario, contacto_id: UUID) -> ContactoEmergencia:
    # El de otro usuario responde igual que uno inexistente: no se revela que existe
    contacto = repo.obtener_de_usuario(db, usuario.id, contacto_id)
    if contacto is None:
        raise NoEncontrado("El contacto no existe", codigo="CONTACTO_NO_ENCONTRADO")
    return contacto


def actualizar(db: Session, usuario: Usuario, contacto_id: UUID, cambios: ContactoCambiosIn) -> ContactoEmergencia:
    contacto = _propio(db, usuario, contacto_id)
    campos = cambios.model_dump(exclude_unset=True)
    if "telefono" in campos:
        _telefono_libre(db, usuario, campos["telefono"], excluir_id=contacto.id)
    contacto = repo.actualizar(db, contacto, **campos)
    db.commit()
    return contacto


def eliminar(db: Session, usuario: Usuario, contacto_id: UUID) -> None:
    repo.eliminar(db, _propio(db, usuario, contacto_id))
    db.commit()
