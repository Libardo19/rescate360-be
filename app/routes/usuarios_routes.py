"""Rutas de usuarios: solo declaran verbo, respuesta y controller.

Las rutas `/me/...` van antes que las de `/{usuario_id}` (A3) para que "me" no se lea como un id.
"""

from fastapi import APIRouter

from app.controllers import usuarios_controller
from app.schemas.usuarios_schema import ConsentimientoOut, DispositivoOut, UbicacionOut, UsuarioOut

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

router.get("/me", response_model=UsuarioOut, summary="Mi perfil")(usuarios_controller.obtener_me)

router.patch(
    "/me/ubicacion", response_model=UbicacionOut, summary="Guardar mi ubicación actual (para alertas por zona)"
)(usuarios_controller.actualizar_ubicacion)

router.get(
    "/me/consentimientos", response_model=list[ConsentimientoOut], summary="Historial de mis autorizaciones"
)(usuarios_controller.listar_consentimientos)

router.post(
    "/me/consentimientos", status_code=201, response_model=ConsentimientoOut, summary="Dar o retirar una autorización"
)(usuarios_controller.registrar_consentimiento)

router.post(
    "/me/dispositivo", response_model=DispositivoOut, summary="Registrar el token push de este teléfono"
)(usuarios_controller.registrar_dispositivo)

router.delete(
    "/me/dispositivo/{token_push}", status_code=204, summary="Quitar el token push al cerrar sesión"
)(usuarios_controller.eliminar_dispositivo)
