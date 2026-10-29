"""Rutas de la guía de emergencia (A7). Leer: cualquier usuario con sesión; editar: super admin."""

from fastapi import APIRouter, Depends

from app.controllers import guia_emergencia_controller
from app.middlewares.auth_middleware import get_current_user
from app.middlewares.role_middleware import require_role
from app.models.enums import RolUsuario
from app.schemas.guia_emergencia_schema import GuiaOut

router = APIRouter(prefix="/guia-emergencia", tags=["guía de emergencia"])
_con_sesion = [Depends(get_current_user)]
_solo_super_admin = [Depends(require_role(RolUsuario.SUPER_ADMIN))]

router.get("", response_model=list[GuiaOut], summary="Guía por categoría", dependencies=_con_sesion)(
    guia_emergencia_controller.listar_guias
)

router.get("/{guia_id}", response_model=GuiaOut, summary="Una guía", dependencies=_con_sesion)(
    guia_emergencia_controller.obtener_guia
)

router.post(
    "", status_code=201, response_model=GuiaOut, summary="Crear una guía (super admin)", dependencies=_solo_super_admin
)(guia_emergencia_controller.crear_guia)

router.patch(
    "/{guia_id}", response_model=GuiaOut, summary="Editar una guía (super admin)", dependencies=_solo_super_admin
)(guia_emergencia_controller.actualizar_guia)

router.delete(
    "/{guia_id}", status_code=204, summary="Borrar una guía (super admin)", dependencies=_solo_super_admin
)(guia_emergencia_controller.eliminar_guia)
