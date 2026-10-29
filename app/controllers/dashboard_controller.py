"""HTTP del dashboard: arma la respuesta y llama al service. Sin SQL ni reglas."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.usuario import Usuario
from app.schemas.dashboard_schema import DashboardOut
from app.services import dashboard_service


def obtener_dashboard(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardOut:
    return dashboard_service.obtener(db, usuario)
