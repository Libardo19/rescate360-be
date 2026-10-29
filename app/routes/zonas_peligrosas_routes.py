"""Rutas de zonas peligrosas: solo declaran verbo, respuesta y controller."""

from fastapi import APIRouter, Depends

from app.controllers import zonas_peligrosas_controller
from app.middlewares.role_middleware import ROLES_ADMIN, require_role
from app.schemas.zonas_peligrosas_schema import ZonaPeligrosaOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix="/zonas-peligrosas", tags=["zonas-peligrosas"])

router.get(
    "",
    response_model=Pagina[ZonaPeligrosaOut],
    summary="Zonas peligrosas visibles según el rol (con lat y lng, por cercanía)",
)(zonas_peligrosas_controller.listar_zonas)

router.post(
    "",
    status_code=201,
    response_model=ZonaPeligrosaOut,
    summary="Crear una zona peligrosa (administrador)",
    dependencies=[Depends(require_role(*ROLES_ADMIN))],
)(zonas_peligrosas_controller.crear_zona)

router.patch(
    "/{zona_id}",
    response_model=ZonaPeligrosaOut,
    summary="Modificar o cambiar el estado de una zona (administrador)",
    dependencies=[Depends(require_role(*ROLES_ADMIN))],
)(zonas_peligrosas_controller.modificar_zona)
