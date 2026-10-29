"""Rutas del dashboard (A7, solo backend)."""

from fastapi import APIRouter, Depends

from app.controllers import dashboard_controller
from app.middlewares.role_middleware import ROLES_OPERATIVOS, require_role
from app.schemas.dashboard_schema import DashboardOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

router.get(
    "",
    response_model=DashboardOut,
    summary="Resumen según el rol: voluntario y admin su organización, super admin todo el sistema",
    dependencies=[Depends(require_role(*ROLES_OPERATIVOS))],
)(dashboard_controller.obtener_dashboard)
