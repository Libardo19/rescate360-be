"""Seed de demostración (idempotente) y matriz de permisos por rol de los endpoints sensibles."""

import pytest
from sqlalchemy import func, select

from app.models.enums import RolUsuario
from app.models.reporte import Reporte
from app.models.usuario import Usuario
from scripts.seed.datos_demo import DOMINIO, sembrar

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN


def test_el_seed_crea_todo_y_es_idempotente(db, cliente):
    sembrar(db, "clave-demo-123")
    usuarios = db.scalar(select(func.count()).select_from(Usuario).where(Usuario.email.like(f"%@{DOMINIO}")))
    reportes = db.scalar(select(func.count()).select_from(Reporte))
    sembrar(db, "clave-demo-123")
    assert db.scalar(select(func.count()).select_from(Usuario).where(Usuario.email.like(f"%@{DOMINIO}"))) == usuarios == 4
    assert db.scalar(select(func.count()).select_from(Reporte)) == reportes

    # Los usuarios de demo pueden entrar
    r = cliente.post("/auth/login", json={"email": f"ciudadano@{DOMINIO}", "password": "clave-demo-123"})
    assert r.status_code == 200, r.text


# (método, ruta, cuerpo) → roles que pasan la autorización. Los demás reciben 403.
MATRIZ = [
    ("GET", "/dashboard", None, {V, A, S}),
    ("GET", "/auditoria", None, {A, S}),
    ("GET", "/usuarios", None, {A, S}),
    ("GET", "/donaciones", None, {A, S}),
    ("GET", "/check-ins", None, {A, S}),
    ("POST", "/alertas", {}, {A, S}),
    ("POST", "/campanas", {}, {A, S}),
    ("POST", "/guia-emergencia", {}, {S}),
    ("POST", "/sismos/simular", None, {S}),
    # Voluntario y administrador solo reciben su propia organización (A3)
    ("GET", "/organizaciones", None, {V, A, S}),
    # Abiertos a cualquier usuario con sesión
    ("GET", "/alertas", None, {C, V, A, S}),
    ("GET", "/sismos", None, {C, V, A, S}),
    ("GET", "/campanas", None, {C, V, A, S}),
    ("GET", "/guia-emergencia", None, {C, V, A, S}),
    ("GET", "/personas-desaparecidas", None, {C, V, A, S}),
    ("GET", "/usuarios/me/datos", None, {C, V, A, S}),
]


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo", "permitidos"), MATRIZ, ids=[f"{m} {r}" for m, r, _, _ in MATRIZ])
@pytest.mark.parametrize("rol", [C, V, A, S], ids=lambda r: r.value)
def test_matriz_de_permisos(cliente, crear_usuario, headers_de, encolados, metodo, ruta, cuerpo, permitidos, rol):
    r = cliente.request(metodo, ruta, json=cuerpo, headers=headers_de(crear_usuario(rol)))
    if rol in permitidos:
        # Pasa la autorización: puede fallar después por datos (422), pero nunca por permiso
        assert r.status_code not in (401, 403), f"{rol.value} debería poder: {r.status_code} {r.text}"
    else:
        assert r.status_code == 403, f"{rol.value} no debería poder: {r.status_code}"


def test_sin_sesion_todo_pide_login(cliente):
    for metodo, ruta, cuerpo, _ in MATRIZ:
        assert cliente.request(metodo, ruta, json=cuerpo).status_code == 401, ruta
