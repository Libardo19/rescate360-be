"""Rutas de campañas y donaciones (B5). La app no procesa pagos."""

from fastapi import APIRouter, Depends

from app.controllers import donaciones_controller
from app.middlewares.role_middleware import ROLES_ADMIN, require_role
from app.schemas.donaciones_schema import CampanaOut, DonacionOut
from app.utils.paginacion import Pagina

router = APIRouter(tags=["donaciones"])
_solo_admin = [Depends(require_role(*ROLES_ADMIN))]

router.get(
    "/campanas", response_model=list[CampanaOut], summary="Campañas vigentes (todas=true: también las cerradas, admin)"
)(donaciones_controller.listar_campanas)

router.post(
    "/campanas", status_code=201, response_model=CampanaOut, summary="Crear una campaña (administrador)",
    dependencies=_solo_admin,
)(donaciones_controller.crear_campana)

router.patch(
    "/campanas/{campana_id}", response_model=CampanaOut, summary="Editar o cerrar una campaña (administrador)",
    dependencies=_solo_admin,
)(donaciones_controller.actualizar_campana)

router.get(
    "/donaciones", response_model=Pagina[DonacionOut], summary="Donaciones registradas (administrador: su organización)",
    dependencies=_solo_admin,
)(donaciones_controller.listar_donaciones)

router.post(
    "/donaciones", status_code=201, response_model=DonacionOut, summary="Registrar una donación recibida (administrador)",
    dependencies=_solo_admin,
)(donaciones_controller.registrar_donacion)

router.patch(
    "/donaciones/{donacion_id}/estado", response_model=DonacionOut, summary="Cambiar el estado (recibida, en proceso, entregada)",
    dependencies=_solo_admin,
)(donaciones_controller.cambiar_estado)
