"""Rutas del modo sin conexión (B7 ampliado): sincronización y relevo por Bluetooth."""

from fastapi import APIRouter

from app.controllers import offline_controller
from app.schemas.offline_schema import LlaveOfflineOut, LoteOfflineOut

router = APIRouter(tags=["sin conexión"])

router.get(
    "/usuarios/me/llave-offline",
    response_model=LlaveOfflineOut,
    summary="Mi llave para firmar mensajes sin conexión (guardarla en el almacenamiento seguro del teléfono)",
)(offline_controller.obtener_llave)

router.post(
    "/offline/sync",
    status_code=202,
    response_model=LoteOfflineOut,
    summary="Subir mi cola de mensajes generados sin conexión (solo los míos)",
)(offline_controller.sincronizar)

router.post(
    "/offline/relevo",
    status_code=202,
    response_model=LoteOfflineOut,
    summary="Subir mensajes de otras personas que llegaron por Bluetooth (se verifican con su firma)",
)(offline_controller.relevar)
