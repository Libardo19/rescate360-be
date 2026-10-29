"""HTTP de zonas peligrosas: arma la respuesta y llama al service. Sin SQL ni reglas."""

from typing import Literal
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import EstadoZona
from app.models.usuario import Usuario
from app.schemas.zonas_peligrosas_schema import ZonaPeligrosaIn, ZonaPeligrosaOut, ZonaPeligrosaPatchIn
from app.services import zonas_peligrosas_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def crear_zona(
    datos: ZonaPeligrosaIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ZonaPeligrosaOut:
    return zonas_peligrosas_service.crear_zona(db, usuario, datos)


def listar_zonas(
    lat: float | None = Query(None, ge=-90, le=90, description="Mi ubicación (va junto con lng)"),
    lng: float | None = Query(None, ge=-180, le=180),
    radio_m: float = Query(5000, gt=0, description="Radio en metros alrededor de lat/lng (máximo 50 km)"),
    alcance: Literal["organizacion", "todas"] = Query(
        "organizacion", description="Solo administrador: 'todas' muestra también las de otras organizaciones"
    ),
    estado: EstadoZona | None = Query(None, description="Por defecto, las vigentes. Solo administrador y super_admin"),
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[ZonaPeligrosaOut]:
    items, total = zonas_peligrosas_service.listar_zonas(
        db, usuario, pag, lat=lat, lng=lng, radio_m=radio_m, alcance=alcance, estado=estado
    )
    return Pagina.crear(items, total, pag)


def modificar_zona(
    zona_id: UUID,
    datos: ZonaPeligrosaPatchIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ZonaPeligrosaOut:
    return zonas_peligrosas_service.modificar_zona(db, usuario, zona_id, datos)
