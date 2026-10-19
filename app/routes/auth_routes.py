from fastapi import APIRouter

from app.controllers import auth_controller
from app.schemas.auth_schema import SesionOut

router = APIRouter(prefix="/auth", tags=["auth"])

router.post("/registro", status_code=201, response_model=SesionOut, summary="Registro de ciudadano")(
    auth_controller.registrar
)
router.post("/login", response_model=SesionOut, summary="Iniciar sesión")(auth_controller.login)
router.post("/refresh-token", response_model=SesionOut, summary="Renovar la sesión")(auth_controller.refrescar)
