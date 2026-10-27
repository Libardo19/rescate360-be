"""HTTP de usuarios: arma la respuesta y llama al service. Sin SQL ni reglas."""

from uuid import UUID

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import EstadoUsuario, RolUsuario
from app.models.usuario import Usuario
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.schemas.usuarios_schema import (
    CambioPasswordIn,
    ConsentimientoIn,
    ConsentimientoOut,
    DispositivoIn,
    DispositivoOut,
    InvitacionOut,
    PerfilCambiosIn,
    UbicacionOut,
    UsuarioCambiosIn,
    UsuarioNuevoIn,
    UsuarioOut,
)
from app.services import usuarios_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def obtener_me(usuario: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return UsuarioOut.model_validate(usuario)


def actualizar_ubicacion(
    datos: LatLng,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UbicacionOut:
    usuario = usuarios_service.actualizar_ubicacion(db, usuario, datos)
    return UbicacionOut.model_validate(usuario)


def registrar_consentimiento(
    datos: ConsentimientoIn,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConsentimientoOut:
    ip = request.client.host if request.client else None
    consentimiento = usuarios_service.registrar_consentimiento(db, usuario, datos, ip)
    return ConsentimientoOut.model_validate(consentimiento)


def listar_consentimientos(
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConsentimientoOut]:
    return [ConsentimientoOut.model_validate(c) for c in usuarios_service.listar_consentimientos(db, usuario)]


def registrar_dispositivo(
    datos: DispositivoIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DispositivoOut:
    dispositivo = usuarios_service.registrar_dispositivo(db, usuario, datos)
    return DispositivoOut.model_validate(dispositivo)


def eliminar_dispositivo(
    token_push: str,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    usuarios_service.eliminar_dispositivo(db, usuario, token_push)
    return Response(status_code=204)


def actualizar_me(
    datos: PerfilCambiosIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    return UsuarioOut.model_validate(usuarios_service.actualizar_perfil(db, usuario, datos))


def cambiar_password(
    datos: CambioPasswordIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    usuarios_service.cambiar_password(db, usuario, datos)
    return Response(status_code=204)


# --- Gestión desde el panel (administrador y super admin; el rol lo exige la ruta) ---


def listar_usuarios(
    rol: RolUsuario | None = None,
    estado: EstadoUsuario | None = None,
    q: str | None = None,
    organizacion_id: UUID | None = None,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[UsuarioOut]:
    items, total = usuarios_service.listar_usuarios(
        db, usuario, pag, rol=rol, estado=estado, q=q, organizacion_id=organizacion_id
    )
    return Pagina.crear([UsuarioOut.model_validate(u) for u in items], total, pag)


def crear_voluntario(
    datos: UsuarioNuevoIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitacionOut:
    return usuarios_service.crear_voluntario(db, usuario, datos)


def obtener_usuario(
    usuario_id: UUID,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    return UsuarioOut.model_validate(usuarios_service.obtener_usuario(db, usuario, usuario_id))


def actualizar_usuario(
    usuario_id: UUID,
    datos: UsuarioCambiosIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    return UsuarioOut.model_validate(usuarios_service.actualizar_usuario(db, usuario, usuario_id, datos))


def regenerar_codigo_activacion(
    usuario_id: UUID,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitacionOut:
    return usuarios_service.regenerar_codigo_activacion(db, usuario, usuario_id)
