from fastapi import APIRouter

from app.controllers import mapa_controller
from app.schemas.mapa_schema import MapaOut

router = APIRouter(prefix="/mapa", tags=["mapa"])

router.get("", response_model=MapaOut, summary="Puntos del mapa en vivo (solicitudes, reportes…) según el rol")(
    mapa_controller.obtener_mapa
)
