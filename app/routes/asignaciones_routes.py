from fastapi import APIRouter, Depends

from app.controllers import asignaciones_controller
from app.middlewares.role_middleware import ROLES_OPERATIVOS, require_role
from app.schemas.asignaciones_schema import AsignacionOut
from app.utils.paginacion import Pagina

router = APIRouter(tags=["asignaciones"], dependencies=[Depends(require_role(*ROLES_OPERATIVOS))])

router.post(
    "/solicitudes-ayuda/{solicitud_id}/asignar",
    status_code=201,
    response_model=AsignacionOut,
    summary="Tomar una solicitud de ayuda",
)(asignaciones_controller.asignar_solicitud)

router.post(
    "/reportes/{reporte_id}/asignar",
    status_code=201,
    response_model=AsignacionOut,
    summary="Tomar un reporte",
)(asignaciones_controller.asignar_reporte)

router.get(
    "/asignaciones/mias",
    response_model=Pagina[AsignacionOut],
    summary="Mis asignaciones",
)(asignaciones_controller.listar_mias)

router.patch(
    "/asignaciones/{asignacion_id}",
    response_model=AsignacionOut,
    summary="Finalizar o cancelar mi asignación",
)(asignaciones_controller.actualizar_estado)
