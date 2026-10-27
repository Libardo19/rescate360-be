"""HTTP de usuarios: arma la respuesta y llama al service. Sin SQL ni reglas."""

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.usuario import Usuario
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.schemas.usuarios_schema import (
    ConsentimientoIn,
    ConsentimientoOut,
    DispositivoIn,
    DispositivoOut,
    UbicacionOut,
    UsuarioOut,
)
from app.services import usuarios_service


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
