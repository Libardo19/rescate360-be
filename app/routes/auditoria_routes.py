"""Rutas de auditoría (A7): solo lectura."""

from fastapi import APIRouter, Depends

from app.controllers import auditoria_controller
from app.middlewares.role_middleware import ROLES_ADMIN, require_role
from app.schemas.auditoria_schema import AuditoriaOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

router.get(
    "",
    response_model=Pagina[AuditoriaOut],
    summary="Historial de cambios (admin: su organización; super admin: todo)",
    dependencies=[Depends(require_role(*ROLES_ADMIN))],
)(auditoria_controller.listar_auditoria)
