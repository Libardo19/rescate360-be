"""HTTP de la guía de emergencia: arma la respuesta y llama al service. Sin SQL ni reglas."""

from uuid import UUID

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.guia_emergencia_schema import Categoria, GuiaCambiosIn, GuiaIn, GuiaOut
from app.services import guia_emergencia_service as service


def listar_guias(categoria: Categoria | None = None, db: Session = Depends(get_db)) -> list[GuiaOut]:
    return [GuiaOut.model_validate(g) for g in service.listar(db, categoria)]


def obtener_guia(guia_id: UUID, db: Session = Depends(get_db)) -> GuiaOut:
    return GuiaOut.model_validate(service.obtener(db, guia_id))


def crear_guia(datos: GuiaIn, db: Session = Depends(get_db)) -> GuiaOut:
    return GuiaOut.model_validate(service.crear(db, datos))


def actualizar_guia(guia_id: UUID, datos: GuiaCambiosIn, db: Session = Depends(get_db)) -> GuiaOut:
    return GuiaOut.model_validate(service.actualizar(db, guia_id, datos))


def eliminar_guia(guia_id: UUID, db: Session = Depends(get_db)) -> Response:
    service.eliminar(db, guia_id)
    return Response(status_code=204)
