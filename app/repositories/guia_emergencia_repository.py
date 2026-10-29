from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.guia_emergencia import GuiaEmergencia


def listar(db: Session, categoria: str | None = None) -> list[GuiaEmergencia]:
    consulta = select(GuiaEmergencia).order_by(GuiaEmergencia.categoria, GuiaEmergencia.titulo)
    if categoria is not None:
        consulta = consulta.where(GuiaEmergencia.categoria == categoria)
    return list(db.scalars(consulta))


def contar(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(GuiaEmergencia)) or 0


def obtener_por_id(db: Session, guia_id: UUID) -> GuiaEmergencia | None:
    return db.get(GuiaEmergencia, guia_id)


def crear(db: Session, **campos) -> GuiaEmergencia:
    guia = GuiaEmergencia(**campos)
    db.add(guia)
    db.flush()
    db.refresh(guia)
    return guia


def actualizar(db: Session, guia: GuiaEmergencia, **campos) -> GuiaEmergencia:
    for campo, valor in campos.items():
        setattr(guia, campo, valor)
    db.flush()
    db.refresh(guia)
    return guia


def eliminar(db: Session, guia: GuiaEmergencia) -> None:
    db.delete(guia)
    db.flush()
