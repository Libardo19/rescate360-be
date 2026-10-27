"""Rutas de reportes. `/tipos` va antes de `/{reporte_id}` para que no se lea como un id."""

from fastapi import APIRouter, Depends

from app.controllers import reportes_controller
from app.middlewares.role_middleware import ROLES_ADMIN, require_role
from app.models.enums import RolUsuario
from app.schemas.reportes_schema import ReporteOut, TipoReporteOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix="/reportes", tags=["reportes"])
_solo_admin = [Depends(require_role(*ROLES_ADMIN))]

router.get(
    "/tipos", response_model=list[TipoReporteOut], summary="Tipos sugeridos (el usuario también puede escribir otro)"
)(reportes_controller.listar_tipos)

router.post(
    "", status_code=201, response_model=ReporteOut, summary="Reportar un incidente (multipart, con fotos y videos)"
)(reportes_controller.crear_reporte)

router.get("", response_model=Pagina[ReporteOut], summary="Listar reportes según el rol")(
    reportes_controller.listar_reportes
)

router.get("/{reporte_id}", response_model=ReporteOut, summary="Detalle de un reporte")(
    reportes_controller.obtener_reporte
)

router.patch(
    "/{reporte_id}/verificar", response_model=ReporteOut, summary="Verificar (administrador)", dependencies=_solo_admin
)(reportes_controller.verificar_reporte)

router.patch(
    "/{reporte_id}/rechazar",
    response_model=ReporteOut,
    summary="Rechazar con motivo opcional (administrador)",
    dependencies=_solo_admin,
)(reportes_controller.rechazar_reporte)

router.patch(
    "/{reporte_id}/marcar-duplicado",
    response_model=ReporteOut,
    summary="Marcar como duplicado de otro reporte (administrador)",
    dependencies=_solo_admin,
)(reportes_controller.marcar_duplicado)

router.patch(
    "/{reporte_id}/organizacion",
    response_model=ReporteOut,
    summary="Enrutar el reporte a una organización (super admin)",
    dependencies=[Depends(require_role(RolUsuario.SUPER_ADMIN))],
)(reportes_controller.asignar_organizacion)
