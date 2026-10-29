"""Rutas de alertas por zona (B3)."""

from fastapi import APIRouter, Depends

from app.controllers import alertas_controller
from app.middlewares.role_middleware import ROLES_ADMIN, require_role
from app.schemas.alertas_schema import AlertaOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix="/alertas", tags=["alertas"])
_solo_admin = [Depends(require_role(*ROLES_ADMIN))]

router.post(
    "",
    status_code=201,
    response_model=AlertaOut,
    summary="Publicar una alerta en un círculo (administrador o super admin); avisa por push a quien esté dentro",
    dependencies=_solo_admin,
)(alertas_controller.crear_alerta)

router.get(
    "", response_model=Pagina[AlertaOut], summary="Alertas activas (con lat y lng: las que cubren ese punto)"
)(alertas_controller.listar_alertas)

router.get("/{alerta_id}", response_model=AlertaOut, summary="Detalle de una alerta")(
    alertas_controller.obtener_alerta
)

router.patch(
    "/{alerta_id}", response_model=AlertaOut, summary="Editar o extender la vigencia", dependencies=_solo_admin
)(alertas_controller.actualizar_alerta)

router.post(
    "/{alerta_id}/cancelar", response_model=AlertaOut, summary="Cancelar una alerta activa", dependencies=_solo_admin
)(alertas_controller.cancelar_alerta)
