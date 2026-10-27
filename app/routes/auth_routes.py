from fastapi import APIRouter

from app.controllers import auth_controller
from app.schemas.auth_schema import MensajeOut, SesionOut

router = APIRouter(prefix="/auth", tags=["auth"])

router.post("/registro", status_code=201, response_model=SesionOut, summary="Registro de ciudadano")(
    auth_controller.registrar
)
router.post("/login", response_model=SesionOut, summary="Iniciar sesión")(auth_controller.login)
router.post("/refresh-token", response_model=SesionOut, summary="Renovar la sesión")(auth_controller.refrescar)
router.post("/activar", response_model=SesionOut, summary="Activar una cuenta invitada con su código")(
    auth_controller.activar
)
router.post(
    "/recuperar",
    status_code=202,
    response_model=MensajeOut,
    summary="Olvidé mi contraseña: enviar un código por SMS o correo",
)(auth_controller.recuperar)
router.post(
    "/restablecer", response_model=SesionOut, summary="Poner una contraseña nueva con el código recibido"
)(auth_controller.restablecer)
