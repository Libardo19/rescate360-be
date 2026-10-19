"""Permisos por rol (sección 4 de docs/PLAN_BACKEND.md) sobre endpoints de prueba."""

import pytest
from fastapi import APIRouter, Depends

from app.core.excepciones import SinPermiso
from app.main import app
from app.middlewares.auth_middleware import get_current_user
from app.middlewares.role_middleware import (
    ROLES_ADMIN,
    ROLES_OPERATIVOS,
    alcance_organizacion,
    require_role,
    solo_propio,
    verificar_misma_organizacion,
)
from app.models.enums import EstadoUsuario, RolUsuario

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN

_router = APIRouter(prefix="/_pruebas_roles")


@_router.get("/autenticado")
def _autenticado(usuario=Depends(get_current_user)):
    return {"rol": usuario.rol}


@_router.get("/operativo")
def _operativo(usuario=Depends(require_role(*ROLES_OPERATIVOS))):
    return {"rol": usuario.rol}


@_router.get("/admin")
def _admin(usuario=Depends(require_role(*ROLES_ADMIN))):
    return {"rol": usuario.rol}


@_router.get("/super")
def _super(usuario=Depends(require_role(S))):
    return {"rol": usuario.rol}


app.include_router(_router)


@pytest.mark.parametrize(
    ("ruta", "permitidos"),
    [
        ("/_pruebas_roles/autenticado", {C, V, A, S}),
        ("/_pruebas_roles/operativo", {V, A, S}),  # seguimiento de solicitudes/reportes
        ("/_pruebas_roles/admin", {A, S}),  # verificar reportes, prioridad manual, gestión
        ("/_pruebas_roles/super", {S}),  # organizaciones, administradores, mover recursos
    ],
)
@pytest.mark.parametrize("rol", [C, V, A, S])
def test_matriz_de_roles(cliente, crear_usuario, headers_de, ruta, permitidos, rol):
    r = cliente.get(ruta, headers=headers_de(crear_usuario(rol)))
    if rol in permitidos:
        assert r.status_code == 200
    else:
        assert r.status_code == 403
        assert r.json()["codigo"] == "SIN_PERMISO"


def test_sin_token(cliente):
    r = cliente.get("/_pruebas_roles/autenticado")
    assert r.status_code == 401
    assert r.json() == {"detalle": "Debes iniciar sesión", "codigo": "TOKEN_REQUERIDO"}


def test_token_basura(cliente):
    r = cliente.get("/_pruebas_roles/autenticado", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_INVALIDO"


@pytest.mark.parametrize(("estado", "codigo"), [(EstadoUsuario.BLOQUEADO, "USUARIO_BLOQUEADO"), (EstadoUsuario.EN_ESPERA, "USUARIO_EN_ESPERA")])
def test_usuario_no_activo(cliente, crear_usuario, headers_de, estado, codigo):
    usuario = crear_usuario(V, estado=estado)
    r = cliente.get("/_pruebas_roles/autenticado", headers=headers_de(usuario))
    assert r.status_code == 403
    assert r.json()["codigo"] == codigo


def test_alcance_organizacion(crear_usuario):
    admin = crear_usuario(A)
    assert alcance_organizacion(admin) == admin.organizacion_id
    assert alcance_organizacion(crear_usuario(V)) is not None
    assert alcance_organizacion(crear_usuario(S)) is None
    with pytest.raises(SinPermiso):
        alcance_organizacion(crear_usuario(C))


def test_solo_propio(crear_usuario):
    ciudadano = crear_usuario(C)
    assert solo_propio(ciudadano) == ciudadano.id
    assert solo_propio(crear_usuario(A)) is None


def test_verificar_misma_organizacion(crear_usuario):
    admin = crear_usuario(A)
    verificar_misma_organizacion(admin, admin.organizacion_id)
    verificar_misma_organizacion(crear_usuario(S), admin.organizacion_id)
    with pytest.raises(SinPermiso) as error:
        verificar_misma_organizacion(crear_usuario(A), admin.organizacion_id)
    assert error.value.codigo == "FUERA_DE_ALCANCE"
