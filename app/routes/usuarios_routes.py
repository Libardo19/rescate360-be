"""Rutas de usuarios: solo declaran verbo, respuesta y controller.

Las rutas `/me/...` van antes que las de `/{usuario_id}` (A3) para que "me" no se lea como un id.
"""

from fastapi import APIRouter, Depends

from app.controllers import usuarios_controller
from app.middlewares.role_middleware import ROLES_ADMIN, require_role
from app.schemas.usuarios_schema import ConsentimientoOut, DispositivoOut, InvitacionOut, UbicacionOut, UsuarioOut
from app.utils.paginacion import Pagina

_solo_admin = [Depends(require_role(*ROLES_ADMIN))]

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

router.get("/me", response_model=UsuarioOut, summary="Mi perfil")(usuarios_controller.obtener_me)

router.patch("/me", response_model=UsuarioOut, summary="Editar mi perfil (nombre, teléfono)")(
    usuarios_controller.actualizar_me
)

router.patch("/me/password", status_code=204, summary="Cambiar mi contraseña (pide la actual)")(
    usuarios_controller.cambiar_password
)

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

# --- Gestión desde el panel: administrador (su organización) y super admin ---

router.get(
    "", response_model=Pagina[UsuarioOut], summary="Listar usuarios según el alcance", dependencies=_solo_admin
)(usuarios_controller.listar_usuarios)

router.post(
    "",
    status_code=201,
    response_model=InvitacionOut,
    summary="Invitar a un voluntario (devuelve el código de activación una sola vez)",
    dependencies=_solo_admin,
)(usuarios_controller.crear_voluntario)

router.get(
    "/{usuario_id}", response_model=UsuarioOut, summary="Detalle de un usuario", dependencies=_solo_admin
)(usuarios_controller.obtener_usuario)

router.patch(
    "/{usuario_id}",
    response_model=UsuarioOut,
    summary="Editar datos o bloquear/desbloquear",
    dependencies=_solo_admin,
)(usuarios_controller.actualizar_usuario)

router.post(
    "/{usuario_id}/codigo-activacion",
    response_model=InvitacionOut,
    summary="Generar un código de activación nuevo (el anterior deja de servir)",
    dependencies=_solo_admin,
)(usuarios_controller.regenerar_codigo_activacion)
