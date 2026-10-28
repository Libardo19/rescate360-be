"""Tests de integracion de centros de ayuda."""

from app.models.enums import RolUsuario, TipoOrganizacion
from app.models.organizacion import Organizacion


def _crear_org(db, nombre="OrgTest"):
    org = Organizacion(nombre=nombre, tipo=TipoOrganizacion.ONG)
    db.add(org)
    db.flush()
    return org


def test_listado_publico_funciona(cliente):
    r = cliente.get("/centros-ayuda")
    assert r.status_code == 200
    assert "items" in r.json()


def test_admin_crea_centro_para_su_organizacion(cliente, crear_usuario, headers_de, db):
    org = _crear_org(db)
    admin = crear_usuario(RolUsuario.ADMINISTRADOR, organizacion=org)
    payload = {
        "nombre": "Centro Acopio",
        "tipo": "centro_acopio",
        "estado": "activo",
        "direccion": "Calle 10",
        "lat": 10.4631,
        "lng": -73.2532,
    }
    r = cliente.post("/centros-ayuda", json=payload, headers=headers_de(admin))
    assert r.status_code == 201
    data = r.json()
    assert data["nombre"] == "Centro Acopio"
    assert data["organizacion_id"] == str(org.id)


def test_voluntario_no_puede_crear(cliente, crear_usuario, headers_de, db):
    org = _crear_org(db)
    vol = crear_usuario(RolUsuario.VOLUNTARIO, organizacion=org)
    payload = {
        "nombre": "Centro X",
        "tipo": "albergue",
        "estado": "activo",
        "direccion": "Calle 5",
        "lat": 10.46,
        "lng": -73.25,
    }
    r = cliente.post("/centros-ayuda", json=payload, headers=headers_de(vol))
    assert r.status_code == 403


def test_admin_no_puede_modificar_centro_de_otra_organizacion(cliente, crear_usuario, headers_de, db):
    org1 = _crear_org(db, "Org1")
    org2 = _crear_org(db, "Org2")
    admin1 = crear_usuario(RolUsuario.ADMINISTRADOR, organizacion=org1)
    admin2 = crear_usuario(RolUsuario.ADMINISTRADOR, organizacion=org2)
    payload = {
        "nombre": "Centro Org1",
        "tipo": "albergue",
        "estado": "activo",
        "direccion": "Calle 7",
        "lat": 10.46,
        "lng": -73.25,
    }
    r = cliente.post("/centros-ayuda", json=payload, headers=headers_de(admin1))
    assert r.status_code == 201
    cid = r.json()["id"]
    r2 = cliente.patch(f"/centros-ayuda/{cid}", json={"estado": "inactivo"}, headers=headers_de(admin2))
    assert r2.status_code == 403
