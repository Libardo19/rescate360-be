"""HTTP de campañas y donaciones: arma la respuesta y llama al service. Sin SQL ni reglas."""

from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import EstadoDonacion
from app.models.usuario import Usuario
from app.schemas.donaciones_schema import (
    CampanaCambiosIn,
    CampanaIn,
    CampanaOut,
    Categoria,
    DonacionEstadoIn,
    DonacionIn,
    DonacionOut,
)
from app.services import donaciones_service as service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def listar_campanas(
    todas: bool = False, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CampanaOut]:
    return service.campanas_salida(db, usuario, service.listar_campanas(db, usuario, todas=todas))


def crear_campana(datos: CampanaIn, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> CampanaOut:
    return service.campanas_salida(db, usuario, [service.crear_campana(db, usuario, datos)])[0]


def actualizar_campana(
    campana_id: UUID,
    datos: CampanaCambiosIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampanaOut:
    return service.campanas_salida(db, usuario, [service.actualizar_campana(db, usuario, campana_id, datos)])[0]


def registrar_donacion(
    datos: DonacionIn, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> DonacionOut:
    return DonacionOut.model_validate(service.registrar_donacion(db, usuario, datos))


def listar_donaciones(
    categoria: Categoria | None = None,
    estado: EstadoDonacion | None = None,
    campana_id: UUID | None = None,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[DonacionOut]:
    items, total = service.listar_donaciones(db, usuario, pag, categoria=categoria, estado=estado, campana_id=campana_id)
    return Pagina.crear([DonacionOut.model_validate(d) for d in items], total, pag)


def cambiar_estado(
    donacion_id: UUID,
    datos: DonacionEstadoIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DonacionOut:
    return DonacionOut.model_validate(service.cambiar_estado(db, usuario, donacion_id, datos))
