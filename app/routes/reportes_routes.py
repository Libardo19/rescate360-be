"""Rutas de reportes. `/tipos` va antes de `/{reporte_id}` para que no se lea como un id."""

from fastapi import APIRouter

from app.controllers import reportes_controller
from app.schemas.reportes_schema import ReporteOut, TipoReporteOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix="/reportes", tags=["reportes"])

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
