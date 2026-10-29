"""A7: historial de auditoría por alcance y guía de emergencia."""

import pytest

from app.models.enums import RolUsuario
from app.models.guia_emergencia import GuiaEmergencia
from app.services import guia_emergencia_service
from app.services.guia_emergencia_contenido import GUIAS_INICIALES

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
CONTACTO = {"nombre": "Ana", "telefono": "3001234567"}


# --- auditoría ---


def _editar_perfil(cliente, headers, nombre):
    assert cliente.patch("/usuarios/me", json={"nombre": nombre}, headers=headers).status_code == 200


def test_super_admin_ve_todo_con_actor_y_accion(cliente, crear_usuario, crear_organizacion, headers_de):
    org_a, org_b = crear_organizacion(), crear_organizacion()
    _editar_perfil(cliente, headers_de(crear_usuario(V, organizacion=org_a)), "Vol A")
    _editar_perfil(cliente, headers_de(crear_usuario(V, organizacion=org_b)), "Vol B")

    r = cliente.get("/auditoria", params={"tabla": "usuarios", "operacion": "UPDATE"}, headers=headers_de(crear_usuario(S)))
    assert r.status_code == 200, r.text
    filas = r.json()["items"]
    nombres = {f["actor"]["nombre"] for f in filas if f["actor"]}
    assert {"Vol A", "Vol B"} <= nombres
    fila = next(f for f in filas if f["actor"] and f["actor"]["nombre"] == "Vol A")
    assert fila["modulo"] == "Usuarios" and fila["accion"].startswith("Actualizó Usuarios (")
    assert "nombre" in fila["campos_modificados"]
    assert "password_hash" not in (fila["datos_nuevos"] or {})


def test_administrador_solo_ve_lo_de_su_organizacion(cliente, crear_usuario, crear_organizacion, headers_de):
    org_a, org_b = crear_organizacion(), crear_organizacion()
    vol_a = crear_usuario(V, organizacion=org_a)
    _editar_perfil(cliente, headers_de(vol_a), "Vol A")
    _editar_perfil(cliente, headers_de(crear_usuario(V, organizacion=org_b)), "Vol B")

    filas = cliente.get("/auditoria", headers=headers_de(crear_usuario(A, organizacion=org_a))).json()["items"]
    assert filas and all(f["actor"] and f["actor"]["id"] == str(vol_a.id) for f in filas)


def test_filtros_por_registro_y_usuario(cliente, crear_usuario, headers_de):
    ciudadano = crear_usuario(C)
    h = headers_de(ciudadano)
    contacto = cliente.post("/usuarios/me/contactos-emergencia", json=CONTACTO, headers=h).json()
    s = headers_de(crear_usuario(S))
    por_registro = cliente.get("/auditoria", params={"registro_id": contacto["id"]}, headers=s).json()
    assert por_registro["total"] == 1 and por_registro["items"][0]["accion"] == "Creó Contactos"
    por_usuario = cliente.get("/auditoria", params={"usuario_id": str(ciudadano.id)}, headers=s).json()
    assert por_usuario["total"] >= 1


@pytest.mark.parametrize("rol", [C, V])
def test_sin_acceso_para_ciudadano_y_voluntario(cliente, crear_usuario, headers_de, rol):
    assert cliente.get("/auditoria", headers=headers_de(crear_usuario(rol))).status_code == 403


# --- guía de emergencia ---


@pytest.fixture
def guia_cargada(db):
    db.query(GuiaEmergencia).delete()
    db.flush()
    assert guia_emergencia_service.cargar_iniciales(db) == len(GUIAS_INICIALES)
    # Idempotente: la segunda vez no crea nada
    assert guia_emergencia_service.cargar_iniciales(db) == 0


def test_todos_leen_la_guia_por_categoria(cliente, crear_usuario, headers_de, guia_cargada):
    h = headers_de(crear_usuario(C))
    todas = cliente.get("/guia-emergencia", headers=h).json()
    assert len(todas) == len(GUIAS_INICIALES)
    desaparecidos = cliente.get("/guia-emergencia", params={"categoria": "desaparecidos"}, headers=h).json()
    assert len(desaparecidos) == 1
    assert any("Mecanismo de Búsqueda Urgente" in p for p in desaparecidos[0]["pasos"])
    assert cliente.get("/guia-emergencia", params={"categoria": "otra"}, headers=h).status_code == 422
    assert cliente.get("/guia-emergencia").status_code == 401


def test_super_admin_crea_edita_y_borra(cliente, crear_usuario, headers_de):
    s = headers_de(crear_usuario(S))
    r = cliente.post(
        "/guia-emergencia",
        json={"titulo": "Tormenta eléctrica", "categoria": "general", "pasos": ["  Aléjate de árboles  ", "", "No uses el celular a la intemperie"]},
        headers=s,
    )
    assert r.status_code == 201, r.text
    guia = r.json()
    assert guia["pasos"] == ["Aléjate de árboles", "No uses el celular a la intemperie"]
    r = cliente.patch(f"/guia-emergencia/{guia['id']}", json={"pasos": ["Busca refugio"]}, headers=s)
    assert r.json()["pasos"] == ["Busca refugio"] and r.json()["titulo"] == "Tormenta eléctrica"
    assert cliente.delete(f"/guia-emergencia/{guia['id']}", headers=s).status_code == 204
    r = cliente.get(f"/guia-emergencia/{guia['id']}", headers=s)
    assert r.status_code == 404 and r.json()["codigo"] == "GUIA_NO_ENCONTRADA"


@pytest.mark.parametrize("rol", [C, V, A])
def test_solo_el_super_admin_edita(cliente, crear_usuario, headers_de, rol):
    r = cliente.post(
        "/guia-emergencia",
        json={"titulo": "Prueba", "categoria": "general", "pasos": ["Paso"]},
        headers=headers_de(crear_usuario(rol)),
    )
    assert r.status_code == 403


def test_guia_sin_pasos_no_vale(cliente, crear_usuario, headers_de):
    r = cliente.post(
        "/guia-emergencia",
        json={"titulo": "Vacía", "categoria": "general", "pasos": ["  "]},
        headers=headers_de(crear_usuario(S)),
    )
    assert r.status_code == 422
