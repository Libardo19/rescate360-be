"""Rutas de organizaciones: solo declaran verbo, respuesta y controller.

Leer: voluntario, administrador (solo la suya) y super admin. Escribir: solo super admin.
"""

from fastapi import APIRouter, Depends

from app.controllers import organizaciones_controller
from app.middlewares.role_middleware import ROLES_OPERATIVOS, require_role
from app.models.enums import RolUsuario
from app.schemas.organizaciones_schema import OrganizacionOut
from app.schemas.usuarios_schema import InvitacionOut, UsuarioOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix="/organizaciones", tags=["organizaciones"])

_operativos = [Depends(require_role(*ROLES_OPERATIVOS))]
_solo_super_admin = [Depends(require_role(RolUsuario.SUPER_ADMIN))]

router.get(
    "", response_model=Pagina[OrganizacionOut], summary="Listar organizaciones (la propia, o todas el super admin)",
    dependencies=_operativos,
)(organizaciones_controller.listar)

router.post(
    "", status_code=201, response_model=OrganizacionOut, summary="Crear una organización",
    dependencies=_solo_super_admin,
)(organizaciones_controller.crear)

router.get(
    "/{organizacion_id}", response_model=OrganizacionOut, summary="Detalle de una organización",
    dependencies=_operativos,
)(organizaciones_controller.obtener)

router.patch(
    "/{organizacion_id}", response_model=OrganizacionOut, summary="Editar o activar/desactivar una organización",
    dependencies=_solo_super_admin,
)(organizaciones_controller.actualizar)

router.get(
    "/{organizacion_id}/administradores", response_model=Pagina[UsuarioOut],
    summary="Administradores de la organización", dependencies=_solo_super_admin,
)(organizaciones_controller.listar_administradores)

router.post(
    "/{organizacion_id}/administradores", status_code=201, response_model=InvitacionOut,
    summary="Invitar a un administrador (devuelve el código de activación una sola vez)",
    dependencies=_solo_super_admin,
)(organizaciones_controller.crear_administrador)

router.delete(
    "/{organizacion_id}/administradores/{usuario_id}", response_model=UsuarioOut,
    summary="Revocar a un administrador (queda bloqueado)", dependencies=_solo_super_admin,
)(organizaciones_controller.revocar_administrador)
