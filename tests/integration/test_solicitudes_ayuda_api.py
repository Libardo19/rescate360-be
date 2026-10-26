"""Pruebas de la API de solicitudes_ayuda (TestClient + BD de pruebas)."""

from uuid import UUID

import pytest

from app.models.enums import RolUsuario
from app.models.solicitud_ayuda import SolicitudAyuda

URL = "/solicitudes-ayuda"
CUERPO = {
    "descripcion": "Necesito agua y alimentos para tres personas",
    "tipo": "alimentaria",
    "ubicacion": {"lat": 10.4631, "lng": -73.2532},
    "direccion": "Calle 16 # 12-34",
}


def _crear(cliente, headers, **cambios) -> dict:
    r = cliente.post(URL, json={**CUERPO, **cambios}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _enrutar(db, solicitud_id: str, *, objetivo=None, manual=None) -> None:
    """Simula el enrutamiento (hoy lo haría la IA o el super_admin)."""
    solicitud = db.get(SolicitudAyuda, UUID(solicitud_id))
    solicitud.organizacion_objetivo_id = objetivo
    solicitud.organizacion_manual_id = manual
    db.flush()


# --- crear -----------------------------------------------------------------------------------


def test_ciudadano_crea_solicitud_pendiente_sin_organizacion(cliente, crear_usuario, headers_de):
    ciudadano = crear_usuario()
    cuerpo = _crear(cliente, headers_de(ciudadano))

    assert cuerpo["usuario_id"] == str(ciudadano.id)
    assert cuerpo["origen"] == "manual"
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["prioridad_ia"] == "pendiente"
    assert cuerpo["prioridad_efectiva"] == "pendiente"
    assert cuerpo["organizacion_efectiva_id"] is None
    assert cuerpo["direccion"] == "Calle 16 # 12-34"
    assert cuerpo["ubicacion"]["lat"] == pytest.approx(10.4631)
    assert cuerpo["ubicacion"]["lng"] == pytest.approx(-73.2532)


def test_sos_nace_critico_y_de_rescate(cliente, crear_usuario, headers_de):
    ciudadano = crear_usuario()
    r = cliente.post(f"{URL}/sos", json={"ubicacion": CUERPO["ubicacion"]}, headers=headers_de(ciudadano))

    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["origen"] == "sos"
    assert cuerpo["tipo"] == "rescate"
    assert cuerpo["prioridad_ia"] == "critica"
    assert cuerpo["prioridad_efectiva"] == "critica"
    assert cuerpo["estado"] == "pendiente"


def test_sin_token_responde_401(cliente):
    r = cliente.post(URL, json=CUERPO)
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_REQUERIDO"


@pytest.mark.parametrize(
    "cambio",
    [
        {"ubicacion": {"lat": 200, "lng": -73.25}},
        {"tipo": "inventado"},
        {"descripcion": "  "},
    ],
)
def test_datos_invalidos_responden_422(cliente, crear_usuario, headers_de, cambio):
    r = cliente.post(URL, json={**CUERPO, **cambio}, headers=headers_de(crear_usuario()))
    assert r.status_code == 422
    assert r.json()["codigo"] == "DATOS_INVALIDOS"


# --- listar y detalle -------------------------------------------------------------------------


def test_ciudadano_solo_lista_las_suyas(cliente, crear_usuario, headers_de):
    ana, beto = crear_usuario(), crear_usuario()
    propia = _crear(cliente, headers_de(ana))
    _crear(cliente, headers_de(beto))

    r = cliente.get(URL, headers=headers_de(ana))

    assert r.status_code == 200, r.text
    assert [s["id"] for s in r.json()["items"]] == [propia["id"]]
    assert r.json()["total"] == 1


def test_paginacion(cliente, crear_usuario, headers_de):
    ciudadano = crear_usuario()
    for _ in range(3):
        _crear(cliente, headers_de(ciudadano))

    r = cliente.get(URL, params={"pagina": 1, "por_pagina": 2}, headers=headers_de(ciudadano))

    cuerpo = r.json()
    assert len(cuerpo["items"]) == 2
    assert cuerpo["total"] == 3
    assert cuerpo["pagina"] == 1
    assert cuerpo["por_pagina"] == 2


def test_administrador_no_ve_solicitudes_sin_enrutar_pero_super_admin_si(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    super_admin = crear_usuario(RolUsuario.SUPER_ADMIN)
    solicitud = _crear(cliente, headers_de(crear_usuario()))

    assert cliente.get(URL, headers=headers_de(admin)).json()["total"] == 0
    assert cliente.get(f"{URL}/{solicitud['id']}", headers=headers_de(admin)).status_code == 403

    r = cliente.get(URL, headers=headers_de(super_admin))
    assert solicitud["id"] in [s["id"] for s in r.json()["items"]]


def test_administrador_ve_la_solicitud_enrutada_a_su_organizacion(cliente, db, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    solicitud = _crear(cliente, headers_de(crear_usuario()))
    _enrutar(db, solicitud["id"], objetivo=admin.organizacion_id)

    lista = cliente.get(URL, headers=headers_de(admin)).json()
    detalle = cliente.get(f"{URL}/{solicitud['id']}", headers=headers_de(admin))

    assert [s["id"] for s in lista["items"]] == [solicitud["id"]]
    assert detalle.status_code == 200
    assert detalle.json()["organizacion_efectiva_id"] == str(admin.organizacion_id)


def test_la_organizacion_manual_prevalece_sobre_la_sugerida(cliente, db, crear_usuario, headers_de):
    admin_a = crear_usuario(RolUsuario.ADMINISTRADOR)
    admin_b = crear_usuario(RolUsuario.ADMINISTRADOR)
    solicitud = _crear(cliente, headers_de(crear_usuario()))
    _enrutar(db, solicitud["id"], objetivo=admin_a.organizacion_id, manual=admin_b.organizacion_id)

    assert cliente.get(URL, headers=headers_de(admin_a)).json()["total"] == 0
    assert cliente.get(URL, headers=headers_de(admin_b)).json()["total"] == 1


def test_ciudadano_no_ve_la_solicitud_de_otro(cliente, crear_usuario, headers_de):
    solicitud = _crear(cliente, headers_de(crear_usuario()))
    r = cliente.get(f"{URL}/{solicitud['id']}", headers=headers_de(crear_usuario()))
    assert r.status_code == 403
    assert r.json()["codigo"] == "SOLICITUD_FUERA_DE_ALCANCE"


def test_solicitud_inexistente_responde_404(cliente, crear_usuario, headers_de):
    from uuid import uuid4

    r = cliente.get(f"{URL}/{uuid4()}", headers=headers_de(crear_usuario()))
    assert r.status_code == 404
    assert r.json()["codigo"] == "SOLICITUD_NO_ENCONTRADA"


# --- prioridad y estado (solo administrador) --------------------------------------------------


def test_ciudadano_no_puede_cambiar_prioridad_ni_estado(cliente, crear_usuario, headers_de):
    ciudadano = crear_usuario()
    solicitud = _crear(cliente, headers_de(ciudadano))

    r1 = cliente.patch(
        f"{URL}/{solicitud['id']}/prioridad", json={"prioridad_manual": "alta"}, headers=headers_de(ciudadano)
    )
    r2 = cliente.patch(f"{URL}/{solicitud['id']}/estado", json={"estado": "atendida"}, headers=headers_de(ciudadano))

    assert r1.status_code == 403
    assert r2.status_code == 403


def test_administrador_define_prioridad_manual_y_prevalece_sobre_la_ia(cliente, db, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    solicitud = _crear(cliente, headers_de(crear_usuario()))
    _enrutar(db, solicitud["id"], objetivo=admin.organizacion_id)

    r = cliente.patch(
        f"{URL}/{solicitud['id']}/prioridad", json={"prioridad_manual": "alta"}, headers=headers_de(admin)
    )

    assert r.status_code == 200, r.text
    assert r.json()["prioridad_manual"] == "alta"
    assert r.json()["prioridad_ia"] == "pendiente"
    assert r.json()["prioridad_efectiva"] == "alta"


def test_prioridad_manual_pendiente_se_rechaza(cliente, db, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    solicitud = _crear(cliente, headers_de(crear_usuario()))
    _enrutar(db, solicitud["id"], objetivo=admin.organizacion_id)

    r = cliente.patch(
        f"{URL}/{solicitud['id']}/prioridad", json={"prioridad_manual": "pendiente"}, headers=headers_de(admin)
    )

    assert r.status_code == 422
    assert r.json()["codigo"] == "DATOS_INVALIDOS"


def test_administrador_de_otra_organizacion_no_puede_modificar(cliente, db, crear_usuario, headers_de):
    admin_a = crear_usuario(RolUsuario.ADMINISTRADOR)
    admin_b = crear_usuario(RolUsuario.ADMINISTRADOR)
    solicitud = _crear(cliente, headers_de(crear_usuario()))
    _enrutar(db, solicitud["id"], objetivo=admin_a.organizacion_id)

    r = cliente.patch(f"{URL}/{solicitud['id']}/estado", json={"estado": "cancelada"}, headers=headers_de(admin_b))

    assert r.status_code == 403
    assert r.json()["codigo"] == "FUERA_DE_ALCANCE"


def test_administrador_cambia_el_estado(cliente, db, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    solicitud = _crear(cliente, headers_de(crear_usuario()))
    _enrutar(db, solicitud["id"], objetivo=admin.organizacion_id)

    r = cliente.patch(f"{URL}/{solicitud['id']}/estado", json={"estado": "en_proceso"}, headers=headers_de(admin))

    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "en_proceso"
