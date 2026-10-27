"""Pruebas de la API de asignaciones (TestClient + BD de pruebas)."""

from uuid import UUID, uuid4

import pytest

from app.models.enums import EstadoSolicitud, RolUsuario
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.utils.geo import punto_desde_latlng

SOLICITUDES = "/solicitudes-ayuda"
REPORTES = "/reportes"
ASIGNACIONES = "/asignaciones"
CUERPO_SOLICITUD = {
    "descripcion": "Familia atrapada por la creciente del río",
    "tipo": "rescate",
    "ubicacion": {"lat": 10.4631, "lng": -73.2532},
}


# --- ayudas de las pruebas -------------------------------------------------------------------


def _crear_solicitud(cliente, headers) -> dict:
    r = cliente.post(SOLICITUDES, json=CUERPO_SOLICITUD, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _enrutar(db, solicitud_id: str, organizacion_id) -> None:
    """Simula el enrutamiento (hoy lo haría la IA o el super_admin)."""
    solicitud = db.get(SolicitudAyuda, UUID(solicitud_id))
    solicitud.organizacion_objetivo_id = organizacion_id
    db.flush()


def _caso(cliente, db, crear_usuario, headers_de):
    """Un voluntario y una solicitud ya enrutada a su organización."""
    voluntario = crear_usuario(RolUsuario.VOLUNTARIO)
    solicitud = _crear_solicitud(cliente, headers_de(crear_usuario()))
    _enrutar(db, solicitud["id"], voluntario.organizacion_id)
    return voluntario, solicitud


def _companero(db, voluntario, crear_usuario):
    """Otro voluntario de la MISMA organización."""
    otro = crear_usuario(RolUsuario.VOLUNTARIO)
    otro.organizacion_id = voluntario.organizacion_id
    db.flush()
    return otro


def _tomar(cliente, headers, solicitud_id: str):
    return cliente.post(f"{SOLICITUDES}/{solicitud_id}/asignar", headers=headers)


def _estado_solicitud(db, solicitud_id: str) -> EstadoSolicitud:
    solicitud = db.get(SolicitudAyuda, UUID(solicitud_id))
    db.refresh(solicitud)
    return solicitud.estado


def _crear_reporte(db, usuario_id, organizacion_id) -> Reporte:
    # Primer valor del enum de tipo, para no depender del nombre del enum
    tipo = "Derrumbe"
    reporte = Reporte(
        usuario_id=usuario_id,
        tipo=tipo,
        descripcion="Árbol caído bloquea la vía",
        ubicacion=punto_desde_latlng(10.4631, -73.2532),
        organizacion_objetivo_id=organizacion_id,
    )
    db.add(reporte)
    db.flush()
    return reporte


# --- tomar una solicitud ---------------------------------------------------------------------


def test_voluntario_toma_la_solicitud_y_esta_pasa_a_en_proceso(cliente, db, crear_usuario, headers_de):
    voluntario, solicitud = _caso(cliente, db, crear_usuario, headers_de)

    r = _tomar(cliente, headers_de(voluntario), solicitud["id"])

    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["solicitud_id"] == solicitud["id"]
    assert cuerpo["reporte_id"] is None
    assert cuerpo["voluntario_id"] == str(voluntario.id)
    assert cuerpo["estado_asignacion"] == "activa"
    assert _estado_solicitud(db, solicitud["id"]) == EstadoSolicitud.EN_PROCESO


def test_dos_voluntarios_pueden_tomar_el_mismo_caso(cliente, db, crear_usuario, headers_de):
    uno, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    dos = _companero(db, uno, crear_usuario)

    r1 = _tomar(cliente, headers_de(uno), solicitud["id"])
    r2 = _tomar(cliente, headers_de(dos), solicitud["id"])

    assert r1.status_code == 201 and r2.status_code == 201
    assert _estado_solicitud(db, solicitud["id"]) == EstadoSolicitud.EN_PROCESO


def test_no_se_puede_tomar_dos_veces_el_mismo_caso(cliente, db, crear_usuario, headers_de):
    voluntario, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    _tomar(cliente, headers_de(voluntario), solicitud["id"])

    r = _tomar(cliente, headers_de(voluntario), solicitud["id"])

    assert r.status_code == 409
    assert r.json()["codigo"] == "ASIGNACION_DUPLICADA"


def test_se_puede_volver_a_tomar_despues_de_cancelar(cliente, db, crear_usuario, headers_de):
    voluntario, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    primera = _tomar(cliente, headers_de(voluntario), solicitud["id"]).json()
    cliente.patch(f"{ASIGNACIONES}/{primera['id']}", json={"estado": "cancelada"}, headers=headers_de(voluntario))

    r = _tomar(cliente, headers_de(voluntario), solicitud["id"])

    assert r.status_code == 201, r.text


def test_voluntario_de_otra_organizacion_no_puede_tomarla(cliente, db, crear_usuario, headers_de):
    _, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    ajeno = crear_usuario(RolUsuario.VOLUNTARIO)

    r = _tomar(cliente, headers_de(ajeno), solicitud["id"])

    assert r.status_code == 403
    assert r.json()["codigo"] == "FUERA_DE_ALCANCE"


def test_solicitud_sin_enrutar_solo_la_toma_el_super_admin(cliente, crear_usuario, headers_de):
    solicitud = _crear_solicitud(cliente, headers_de(crear_usuario()))

    r_voluntario = _tomar(cliente, headers_de(crear_usuario(RolUsuario.VOLUNTARIO)), solicitud["id"])
    r_super = _tomar(cliente, headers_de(crear_usuario(RolUsuario.SUPER_ADMIN)), solicitud["id"])

    assert r_voluntario.status_code == 403
    assert r_super.status_code == 201, r_super.text


def test_ciudadano_no_puede_tomar_solicitudes(cliente, crear_usuario, headers_de):
    ciudadano = crear_usuario()
    solicitud = _crear_solicitud(cliente, headers_de(ciudadano))

    assert _tomar(cliente, headers_de(ciudadano), solicitud["id"]).status_code == 403


@pytest.mark.parametrize("cerrada", [EstadoSolicitud.ATENDIDA, EstadoSolicitud.CANCELADA])
def test_solicitud_cerrada_no_se_puede_tomar(cliente, db, crear_usuario, headers_de, cerrada):
    voluntario, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    fila = db.get(SolicitudAyuda, UUID(solicitud["id"]))
    fila.estado = cerrada
    db.flush()

    r = _tomar(cliente, headers_de(voluntario), solicitud["id"])

    assert r.status_code == 409
    assert r.json()["codigo"] == "SOLICITUD_CERRADA"


def test_solicitud_inexistente_responde_404(cliente, crear_usuario, headers_de):
    r = _tomar(cliente, headers_de(crear_usuario(RolUsuario.VOLUNTARIO)), str(uuid4()))
    assert r.status_code == 404
    assert r.json()["codigo"] == "SOLICITUD_NO_ENCONTRADA"


# --- finalizar y cancelar --------------------------------------------------------------------


def test_finalizar_deja_la_solicitud_atendida(cliente, db, crear_usuario, headers_de):
    voluntario, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    asignacion = _tomar(cliente, headers_de(voluntario), solicitud["id"]).json()

    r = cliente.patch(f"{ASIGNACIONES}/{asignacion['id']}", json={"estado": "finalizada"}, headers=headers_de(voluntario))

    assert r.status_code == 200, r.text
    assert r.json()["estado_asignacion"] == "finalizada"
    assert _estado_solicitud(db, solicitud["id"]) == EstadoSolicitud.ATENDIDA


def test_cancelar_la_unica_asignacion_devuelve_la_solicitud_a_pendiente(cliente, db, crear_usuario, headers_de):
    voluntario, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    asignacion = _tomar(cliente, headers_de(voluntario), solicitud["id"]).json()

    r = cliente.patch(f"{ASIGNACIONES}/{asignacion['id']}", json={"estado": "cancelada"}, headers=headers_de(voluntario))

    assert r.status_code == 200, r.text
    assert _estado_solicitud(db, solicitud["id"]) == EstadoSolicitud.PENDIENTE


def test_cancelar_con_otro_voluntario_activo_deja_la_solicitud_en_proceso(cliente, db, crear_usuario, headers_de):
    uno, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    dos = _companero(db, uno, crear_usuario)
    asignacion_uno = _tomar(cliente, headers_de(uno), solicitud["id"]).json()
    _tomar(cliente, headers_de(dos), solicitud["id"])

    cliente.patch(f"{ASIGNACIONES}/{asignacion_uno['id']}", json={"estado": "cancelada"}, headers=headers_de(uno))

    assert _estado_solicitud(db, solicitud["id"]) == EstadoSolicitud.EN_PROCESO


def test_no_se_puede_cambiar_la_asignacion_de_otro(cliente, db, crear_usuario, headers_de):
    uno, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    dos = _companero(db, uno, crear_usuario)
    asignacion = _tomar(cliente, headers_de(uno), solicitud["id"]).json()

    r = cliente.patch(f"{ASIGNACIONES}/{asignacion['id']}", json={"estado": "finalizada"}, headers=headers_de(dos))

    assert r.status_code == 403
    assert r.json()["codigo"] == "ASIGNACION_AJENA"


def test_una_asignacion_cerrada_no_se_puede_volver_a_cerrar(cliente, db, crear_usuario, headers_de):
    voluntario, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    asignacion = _tomar(cliente, headers_de(voluntario), solicitud["id"]).json()
    url = f"{ASIGNACIONES}/{asignacion['id']}"
    cliente.patch(url, json={"estado": "finalizada"}, headers=headers_de(voluntario))

    r = cliente.patch(url, json={"estado": "cancelada"}, headers=headers_de(voluntario))

    assert r.status_code == 409
    assert r.json()["codigo"] == "TRANSICION_NO_PERMITIDA"


def test_el_estado_activa_se_rechaza_con_422(cliente, db, crear_usuario, headers_de):
    voluntario, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    asignacion = _tomar(cliente, headers_de(voluntario), solicitud["id"]).json()

    r = cliente.patch(f"{ASIGNACIONES}/{asignacion['id']}", json={"estado": "activa"}, headers=headers_de(voluntario))

    assert r.status_code == 422
    assert r.json()["codigo"] == "DATOS_INVALIDOS"


def test_asignacion_inexistente_responde_404(cliente, crear_usuario, headers_de):
    r = cliente.patch(
        f"{ASIGNACIONES}/{uuid4()}", json={"estado": "finalizada"}, headers=headers_de(crear_usuario(RolUsuario.VOLUNTARIO))
    )
    assert r.status_code == 404
    assert r.json()["codigo"] == "ASIGNACION_NO_ENCONTRADA"


# --- mis asignaciones ------------------------------------------------------------------------


def test_mias_lista_solo_las_propias_y_filtra_por_estado(cliente, db, crear_usuario, headers_de):
    uno, solicitud = _caso(cliente, db, crear_usuario, headers_de)
    dos = _companero(db, uno, crear_usuario)
    propia = _tomar(cliente, headers_de(uno), solicitud["id"]).json()
    _tomar(cliente, headers_de(dos), solicitud["id"])

    todas = cliente.get(f"{ASIGNACIONES}/mias", headers=headers_de(uno))
    activas = cliente.get(f"{ASIGNACIONES}/mias", params={"estado": "activa"}, headers=headers_de(uno))
    finalizadas = cliente.get(f"{ASIGNACIONES}/mias", params={"estado": "finalizada"}, headers=headers_de(uno))

    assert todas.status_code == 200, todas.text
    assert [a["id"] for a in todas.json()["items"]] == [propia["id"]]
    assert activas.json()["total"] == 1
    assert finalizadas.json()["total"] == 0


def test_ciudadano_no_puede_ver_mias(cliente, crear_usuario, headers_de):
    assert cliente.get(f"{ASIGNACIONES}/mias", headers=headers_de(crear_usuario())).status_code == 403


# --- reportes --------------------------------------------------------------------------------


def test_voluntario_toma_un_reporte_de_su_organizacion(cliente, db, crear_usuario, headers_de):
    voluntario = crear_usuario(RolUsuario.VOLUNTARIO)
    reporte = _crear_reporte(db, crear_usuario().id, voluntario.organizacion_id)

    r = cliente.post(f"{REPORTES}/{reporte.id}/asignar", headers=headers_de(voluntario))

    assert r.status_code == 201, r.text
    assert r.json()["reporte_id"] == str(reporte.id)
    assert r.json()["solicitud_id"] is None
    assert r.json()["estado_asignacion"] == "activa"


def test_voluntario_de_otra_organizacion_no_toma_el_reporte(cliente, db, crear_usuario, headers_de):
    dueno = crear_usuario(RolUsuario.VOLUNTARIO)
    ajeno = crear_usuario(RolUsuario.VOLUNTARIO)
    reporte = _crear_reporte(db, crear_usuario().id, dueno.organizacion_id)

    r = cliente.post(f"{REPORTES}/{reporte.id}/asignar", headers=headers_de(ajeno))

    assert r.status_code == 403


def test_no_se_toma_dos_veces_el_mismo_reporte(cliente, db, crear_usuario, headers_de):
    voluntario = crear_usuario(RolUsuario.VOLUNTARIO)
    reporte = _crear_reporte(db, crear_usuario().id, voluntario.organizacion_id)
    cliente.post(f"{REPORTES}/{reporte.id}/asignar", headers=headers_de(voluntario))

    r = cliente.post(f"{REPORTES}/{reporte.id}/asignar", headers=headers_de(voluntario))

    assert r.status_code == 409
    assert r.json()["codigo"] == "ASIGNACION_DUPLICADA"


def test_reporte_inexistente_responde_404(cliente, crear_usuario, headers_de):
    r = cliente.post(f"{REPORTES}/{uuid4()}/asignar", headers=headers_de(crear_usuario(RolUsuario.VOLUNTARIO)))
    assert r.status_code == 404
    assert r.json()["codigo"] == "REPORTE_NO_ENCONTRADO"


def test_finalizar_una_asignacion_de_reporte_no_toca_solicitudes(cliente, db, crear_usuario, headers_de):
    voluntario = crear_usuario(RolUsuario.VOLUNTARIO)
    reporte = _crear_reporte(db, crear_usuario().id, voluntario.organizacion_id)
    asignacion = cliente.post(f"{REPORTES}/{reporte.id}/asignar", headers=headers_de(voluntario)).json()

    r = cliente.patch(f"{ASIGNACIONES}/{asignacion['id']}", json={"estado": "finalizada"}, headers=headers_de(voluntario))

    assert r.status_code == 200, r.text
    assert r.json()["estado_asignacion"] == "finalizada"
