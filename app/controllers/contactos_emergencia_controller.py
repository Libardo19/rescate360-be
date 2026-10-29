"""HTTP de contactos de emergencia: arma la respuesta y llama al service. Sin SQL ni reglas."""

from uuid import UUID

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.usuario import Usuario
from app.schemas.contactos_emergencia_schema import ContactoCambiosIn, ContactoIn, ContactoOut
from app.services import contactos_emergencia_service as service


def listar_contactos(
    usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ContactoOut]:
    return [ContactoOut.model_validate(c) for c in service.listar(db, usuario)]


def crear_contacto(
    datos: ContactoIn, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> ContactoOut:
    return ContactoOut.model_validate(service.crear(db, usuario, datos))


def actualizar_contacto(
    contacto_id: UUID,
    datos: ContactoCambiosIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactoOut:
    return ContactoOut.model_validate(service.actualizar(db, usuario, contacto_id, datos))


def eliminar_contacto(
    contacto_id: UUID, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    service.eliminar(db, usuario, contacto_id)
    return Response(status_code=204)
