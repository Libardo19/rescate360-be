"""Guía de emergencia (A7).

- Cualquier usuario con sesión la consulta (también se guarda en el teléfono para leerla sin red).
- Crear, editar y borrar: solo el super admin (el documento de roles no se lo da al administrador).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import NoEncontrado
from app.models.guia_emergencia import GuiaEmergencia
from app.repositories import guia_emergencia_repository as repo
from app.schemas.guia_emergencia_schema import GuiaCambiosIn, GuiaIn
from app.services.guia_emergencia_contenido import GUIAS_INICIALES


def listar(db: Session, categoria: str | None) -> list[GuiaEmergencia]:
    return repo.listar(db, categoria)


def obtener(db: Session, guia_id: UUID) -> GuiaEmergencia:
    guia = repo.obtener_por_id(db, guia_id)
    if guia is None:
        raise NoEncontrado("La guía no existe", codigo="GUIA_NO_ENCONTRADA")
    return guia


def crear(db: Session, datos: GuiaIn) -> GuiaEmergencia:
    guia = repo.crear(db, titulo=datos.titulo, categoria=datos.categoria, contenido="\n".join(datos.pasos))
    db.commit()
    return guia


def actualizar(db: Session, guia_id: UUID, cambios: GuiaCambiosIn) -> GuiaEmergencia:
    guia = obtener(db, guia_id)
    campos = cambios.model_dump(exclude_unset=True, exclude_none=True)
    if "pasos" in campos:
        campos["contenido"] = "\n".join(campos.pop("pasos"))
    guia = repo.actualizar(db, guia, **campos)
    db.commit()
    return guia


def eliminar(db: Session, guia_id: UUID) -> None:
    repo.eliminar(db, obtener(db, guia_id))
    db.commit()


def cargar_iniciales(db: Session) -> int:
    """Carga el contenido inicial solo si la tabla está vacía (idempotente). Devuelve cuántas creó."""
    if repo.contar(db) > 0:
        return 0
    for guia in GUIAS_INICIALES:
        repo.crear(db, titulo=guia["titulo"], categoria=guia["categoria"], contenido="\n".join(guia["pasos"]))
    db.commit()
    return len(GUIAS_INICIALES)
