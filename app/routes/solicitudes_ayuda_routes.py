"""Rutas de solicitudes_ayuda: solo declaran verbo, respuesta y controller."""

from fastapi import APIRouter, Depends

from app.controllers import solicitudes_ayuda_controller
from app.middlewares.role_middleware import ROLES_ADMIN, require_role
from app.schemas.solicitudes_ayuda_schema import SolicitudAyudaOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix="/solicitudes-ayuda", tags=["solicitudes-ayuda"])

router.post(
    "", status_code=201, response_model=SolicitudAyudaOut, summary="Crear una solicitud de ayuda"
)(solicitudes_ayuda_controller.crear_solicitud)

router.post(
    "/sos", status_code=201, response_model=SolicitudAyudaOut, summary="SOS: solicitud de emergencia (solo ubicación)"
)(solicitudes_ayuda_controller.crear_sos)

router.get(
    "", response_model=Pagina[SolicitudAyudaOut], summary="Listar solicitudes según el rol"
)(solicitudes_ayuda_controller.listar_solicitudes)

router.get(
    "/{solicitud_id}", response_model=SolicitudAyudaOut, summary="Detalle de una solicitud"
)(solicitudes_ayuda_controller.obtener_solicitud)

router.patch(
    "/{solicitud_id}/prioridad",
    response_model=SolicitudAyudaOut,
    summary="Prioridad manual (administrador)",
    dependencies=[Depends(require_role(*ROLES_ADMIN))],
)(solicitudes_ayuda_controller.actualizar_prioridad)

router.patch(
    "/{solicitud_id}/estado",
    response_model=SolicitudAyudaOut,
    summary="Cambiar el estado (administrador)",
    dependencies=[Depends(require_role(*ROLES_ADMIN))],
)(solicitudes_ayuda_controller.actualizar_estado)
