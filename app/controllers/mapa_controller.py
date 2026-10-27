"""HTTP del mapa: lee la consulta y llama al service. Sin SQL ni reglas."""

from datetime import datetime

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.usuario import Usuario
from app.schemas.mapa_schema import CAPAS_POR_DEFECTO, MapaOut
from app.services import mapa_service


def obtener_mapa(
    lat: float | None = Query(None, ge=-90, le=90, description="Centro del mapa (va junto con lng)"),
    lng: float | None = Query(None, ge=-180, le=180),
    radio_m: float = Query(5000, gt=0, description="Radio en metros alrededor de lat/lng (máximo 50 km)"),
    capas: str = Query(CAPAS_POR_DEFECTO, description="Separadas por coma: solicitudes, reportes, centros, zonas, alertas"),
    desde: datetime | None = Query(None, description="`generado_en` de la respuesta anterior: solo lo que cambió"),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MapaOut:
    return mapa_service.obtener_mapa(db, usuario, lat=lat, lng=lng, radio_m=radio_m, capas=capas, desde=desde)
