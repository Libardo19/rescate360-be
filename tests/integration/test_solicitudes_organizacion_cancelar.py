"""Enrutar una solicitud a mano (super admin) y cancelarla desde la cuenta de quien la creó."""

from uuid import UUID

import pytest

from app.models.asignacion import Asignacion
from app.models.enums import EstadoAsignacion, EstadoSolicitud, RolUsuario
from app.models.solicitud_ayuda import SolicitudAyuda

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
SOLICITUDES = "/solicitudes-ayuda"
CUERPO = {
    "descripcion": "Adulto mayor sin medicamentos",
    "tipo": "medica",
    "ubicacion": {"lat": 10.4631, "lng": -73.2532},
}


def _crear(cliente, headers) -> dict:
    r = cliente.post(SOLICITUDES, json=CUERPO, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _enrutar(cliente, headers, solicitud_id: str, organizacion_id):
    return cliente.patch(
        f"{SOLICITUDES}/{solicitud_id}/organizacion", json={"organizacion_id": str(organizacion_id)}, headers=headers
    )


def _cerrar(db, solicitud_id: str, estado: EstadoSolicitud) -> None:
    solicitud = db.get(SolicitudAyuda, UUID(solicitud_id))
    solicitud.estado = estado
    db.flush()


# --- enrutar a una organización ---


def test_super_admin_enruta_y_la_organizacion_ya_ve_el_caso(cliente, crear_usuario, headers_de):
    super_admin = crear_usuario(S)
    admin = crear_usuario(A)
    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    solicitud = _crear(cliente, headers_de(crear_usuario(C)))

    # Antes de enrutar, la organización no la ve
    assert cliente.get(SOLICITUDES, headers=headers_de(admin)).json()["total"] == 0

    r = _enrutar(cliente, headers_de(super_admin), solicitud["id"], admin.organizacion_id)
    assert r.status_code == 200, r.text
    assert r.json()["organizacion_manual_id"] == str(admin.organizacion_id)

    for usuario in (admin, voluntario):
        r = cliente.get(SOLICITUDES, headers=headers_de(usuario))
        assert [s["id"] for s in r.json()["items"]] == [solicitud["id"]]
    # Y el voluntario la puede tomar
    assert cliente.post(f"{SOLICITUDES}/{solicitud['id']}/asignar", headers=headers_de(voluntario)).status_code == 201


def test_solo_el_super_admin_enruta(cliente, crear_usuario, crear_organizacion, headers_de):
    solicitud = _crear(cliente, headers_de(crear_usuario(C)))
    destino = crear_organizacion()
    for rol in (C, V, A):
        r = _enrutar(cliente, headers_de(crear_usuario(rol)), solicitud["id"], destino.id)
        assert r.status_code == 403


def test_enrutar_a_organizacion_inexistente_o_desactivada(cliente, db, crear_usuario, crear_organizacion, headers_de):
    super_admin = crear_usuario(S)
    solicitud = _crear(cliente, headers_de(crear_usuario(C)))

    r = _enrutar(cliente, headers_de(super_admin), solicitud["id"], "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404 and r.json()["codigo"] == "ORGANIZACION_NO_ENCONTRADA"

    apagada = crear_organizacion()
    apagada.activa = False
    db.flush()
    r = _enrutar(cliente, headers_de(super_admin), solicitud["id"], apagada.id)
    assert r.status_code == 409 and r.json()["codigo"] == "ORGANIZACION_INACTIVA"


def test_enrutar_solicitud_inexistente(cliente, crear_usuario, crear_organizacion, headers_de):
    r = _enrutar(
        cliente, headers_de(crear_usuario(S)), "00000000-0000-0000-0000-000000000000", crear_organizacion().id
    )
    assert r.status_code == 404 and r.json()["codigo"] == "SOLICITUD_NO_ENCONTRADA"


@pytest.mark.parametrize("cerrada", [EstadoSolicitud.ATENDIDA, EstadoSolicitud.CANCELADA])
def test_no_se_enruta_una_solicitud_cerrada(cliente, db, crear_usuario, crear_organizacion, headers_de, cerrada):
    solicitud = _crear(cliente, headers_de(crear_usuario(C)))
    _cerrar(db, solicitud["id"], cerrada)
    r = _enrutar(cliente, headers_de(crear_usuario(S)), solicitud["id"], crear_organizacion().id)
    assert r.status_code == 409 and r.json()["codigo"] == "SOLICITUD_CERRADA"


def test_no_se_mueve_si_ya_la_tomo_un_voluntario(cliente, crear_usuario, crear_organizacion, headers_de):
    super_admin = crear_usuario(S)
    voluntario = crear_usuario(V)
    solicitud = _crear(cliente, headers_de(crear_usuario(C)))
    _enrutar(cliente, headers_de(super_admin), solicitud["id"], voluntario.organizacion_id)
    cliente.post(f"{SOLICITUDES}/{solicitud['id']}/asignar", headers=headers_de(voluntario))

    r = _enrutar(cliente, headers_de(super_admin), solicitud["id"], crear_organizacion().id)
    assert r.status_code == 409 and r.json()["codigo"] == "SOLICITUD_CON_ASIGNACIONES"


# --- el dueño cancela ---


def test_el_dueno_cancela_su_solicitud_pendiente(cliente, crear_usuario, headers_de):
    ciudadano = crear_usuario(C)
    solicitud = _crear(cliente, headers_de(ciudadano))
    r = cliente.post(f"{SOLICITUDES}/{solicitud['id']}/cancelar", headers=headers_de(ciudadano))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelada"


def test_cancelar_en_proceso_cancela_las_asignaciones(cliente, db, crear_usuario, headers_de):
    ciudadano = crear_usuario(C)
    voluntario = crear_usuario(V)
    solicitud = _crear(cliente, headers_de(ciudadano))
    _enrutar(cliente, headers_de(crear_usuario(S)), solicitud["id"], voluntario.organizacion_id)
    asignacion = cliente.post(f"{SOLICITUDES}/{solicitud['id']}/asignar", headers=headers_de(voluntario)).json()

    r = cliente.post(f"{SOLICITUDES}/{solicitud['id']}/cancelar", headers=headers_de(ciudadano))
    assert r.status_code == 200 and r.json()["estado"] == "cancelada"
    fila = db.get(Asignacion, UUID(asignacion["id"]))
    db.refresh(fila)
    assert fila.estado_asignacion == EstadoAsignacion.CANCELADA


def test_nadie_mas_cancela_la_solicitud_ajena(cliente, crear_usuario, headers_de):
    solicitud = _crear(cliente, headers_de(crear_usuario(C)))
    for usuario in (crear_usuario(C), crear_usuario(S)):
        r = cliente.post(f"{SOLICITUDES}/{solicitud['id']}/cancelar", headers=headers_de(usuario))
        assert r.status_code == 403 and r.json()["codigo"] == "SOLICITUD_FUERA_DE_ALCANCE"


@pytest.mark.parametrize("cerrada", [EstadoSolicitud.ATENDIDA, EstadoSolicitud.CANCELADA])
def test_no_se_cancela_una_solicitud_cerrada(cliente, db, crear_usuario, headers_de, cerrada):
    ciudadano = crear_usuario(C)
    solicitud = _crear(cliente, headers_de(ciudadano))
    _cerrar(db, solicitud["id"], cerrada)
    r = cliente.post(f"{SOLICITUDES}/{solicitud['id']}/cancelar", headers=headers_de(ciudadano))
    assert r.status_code == 409 and r.json()["codigo"] == "SOLICITUD_CERRADA"
