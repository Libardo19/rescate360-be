"""Contactos de emergencia (A6): CRUD propio, E.164, máximo 5 y aislamiento entre usuarios."""

import pytest

from app.models.enums import RolUsuario

URL = "/usuarios/me/contactos-emergencia"
CONTACTO = {"nombre": "Carlos  Ruiz ", "telefono": "300 123 4567", "parentesco": "Hermano"}


def _crear(cliente, headers, **campos):
    return cliente.post(URL, json={**CONTACTO, **campos}, headers=headers)


def test_crea_normaliza_y_lista(cliente, crear_usuario, headers_de):
    h = headers_de(crear_usuario())
    r = _crear(cliente, h)
    assert r.status_code == 201, r.text
    assert r.json()["telefono"] == "+573001234567"
    assert r.json()["nombre"] == "Carlos Ruiz"
    _crear(cliente, h, nombre="Ana", telefono="+573109876543", parentesco="")
    lista = cliente.get(URL, headers=h).json()
    assert [c["nombre"] for c in lista] == ["Carlos Ruiz", "Ana"]
    assert lista[1]["parentesco"] is None


@pytest.mark.parametrize("rol", list(RolUsuario))
def test_todos_los_roles_tienen_contactos(cliente, crear_usuario, headers_de, rol):
    assert _crear(cliente, headers_de(crear_usuario(rol))).status_code == 201


@pytest.mark.parametrize("campos", [{"telefono": "123"}, {"nombre": ""}, {"parentesco": "x" * 16}])
def test_validaciones(cliente, crear_usuario, headers_de, campos):
    assert _crear(cliente, headers_de(crear_usuario()), **campos).status_code == 422


def test_maximo_cinco_y_sin_telefonos_repetidos(cliente, crear_usuario, headers_de):
    h = headers_de(crear_usuario())
    assert _crear(cliente, h).status_code == 201
    r = _crear(cliente, h, nombre="Otro", telefono="3001234567")
    assert r.status_code == 409 and r.json()["codigo"] == "CONTACTO_DUPLICADO"
    for i in range(4):
        assert _crear(cliente, h, telefono=f"+57310000000{i}").status_code == 201
    r = _crear(cliente, h, telefono="+573200000000")
    assert r.status_code == 409 and r.json()["codigo"] == "MAXIMO_CONTACTOS"


def test_edita_y_elimina(cliente, crear_usuario, headers_de):
    h = headers_de(crear_usuario())
    contacto = _crear(cliente, h).json()
    r = cliente.patch(f"{URL}/{contacto['id']}", json={"telefono": "3109876543"}, headers=h)
    assert r.status_code == 200 and r.json()["telefono"] == "+573109876543"
    assert r.json()["nombre"] == "Carlos Ruiz"
    r = cliente.patch(f"{URL}/{contacto['id']}", json={"nombre": None}, headers=h)
    assert r.status_code == 422
    assert cliente.delete(f"{URL}/{contacto['id']}", headers=h).status_code == 204
    assert cliente.get(URL, headers=h).json() == []


def test_no_se_ven_ni_tocan_los_de_otro(cliente, crear_usuario, headers_de):
    contacto = _crear(cliente, headers_de(crear_usuario())).json()
    otro = headers_de(crear_usuario())
    assert cliente.get(URL, headers=otro).json() == []
    r = cliente.patch(f"{URL}/{contacto['id']}", json={"nombre": "Hackeado"}, headers=otro)
    assert r.status_code == 404 and r.json()["codigo"] == "CONTACTO_NO_ENCONTRADO"
    assert cliente.delete(f"{URL}/{contacto['id']}", headers=otro).status_code == 404


def test_sin_sesion(cliente):
    assert cliente.get(URL).status_code == 401
