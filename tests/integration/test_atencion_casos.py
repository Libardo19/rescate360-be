"""El voluntario finaliza → el caso se cierra y el panel ve quién lo atendió.

- Finalizar la asignación de un reporte lo deja `atendido` (antes quedaba pendiente/verificado y
  seguía saliendo como activo en la app, el mapa y el panel).
- Solicitudes y reportes traen `atencion` (voluntario, estado, desde, hasta) para la organización
  y el super admin; el ciudadano no la recibe.
"""

from uuid import UUID

import pytest

from app.models.enums import EstadoReporte, RolUsuario
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.utils.geo import punto_desde_latlng

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
PUNTO = (10.4631, -73.2532)


@pytest.fixture
def caso_reporte(db, crear_usuario):
    """Un reporte verificado de la organización de un voluntario, más su admin y el ciudadano autor."""
    voluntario = crear_usuario(V)
    admin = crear_usuario(A, organizacion=None)
    admin.organizacion_id = voluntario.organizacion_id
    ciudadano = crear_usuario(C)
    reporte = Reporte(
        usuario_id=ciudadano.id,
        tipo="incendio",
        descripcion="Humo en una bodega",
        ubicacion=punto_desde_latlng(*PUNTO),
        organizacion_manual_id=voluntario.organizacion_id,
        estado=EstadoReporte.VERIFICADO,
    )
    db.add(reporte)
    db.flush()
    return voluntario, admin, ciudadano, reporte


def _tomar_reporte(cliente, headers, reporte_id) -> dict:
    r = cliente.post(f"/reportes/{reporte_id}/asignar", headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _cerrar(cliente, headers, asignacion_id, estado):
    r = cliente.patch(f"/asignaciones/{asignacion_id}", json={"estado": estado}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# --- reportes ---


def test_finalizar_deja_el_reporte_atendido_y_fuera_del_mapa(cliente, db, headers_de, caso_reporte):
    voluntario, admin, _, reporte = caso_reporte
    hv = headers_de(voluntario)
    asignacion = _tomar_reporte(cliente, hv, reporte.id)
    _cerrar(cliente, hv, asignacion["id"], "finalizada")

    db.refresh(reporte)
    assert reporte.estado == EstadoReporte.ATENDIDO
    # Ya no sale en el mapa ni en los casos abiertos del voluntario
    puntos = cliente.get("/mapa", params={"capas": "reportes"}, headers=hv).json()["puntos"]
    assert str(reporte.id) not in [p["id"] for p in puntos]
    # El admin lo ve atendido y sabe quién y cuándo
    visto = cliente.get(f"/reportes/{reporte.id}", headers=headers_de(admin)).json()
    assert visto["estado"] == "atendido"
    assert visto["atencion"]["voluntario"]["nombre"] == voluntario.nombre
    assert visto["atencion"]["estado"] == "finalizada" and visto["atencion"]["hasta"] is not None


def test_cancelar_no_cierra_el_reporte(cliente, db, headers_de, caso_reporte):
    voluntario, _, _, reporte = caso_reporte
    hv = headers_de(voluntario)
    asignacion = _tomar_reporte(cliente, hv, reporte.id)
    _cerrar(cliente, hv, asignacion["id"], "cancelada")
    db.refresh(reporte)
    assert reporte.estado == EstadoReporte.VERIFICADO
    # Sin asignaciones vigentes no hay "atención"
    assert cliente.get(f"/reportes/{reporte.id}", headers=hv).json()["atencion"] is None


def test_un_reporte_atendido_no_se_vuelve_a_tomar_ni_a_revisar(cliente, db, headers_de, crear_usuario, caso_reporte):
    voluntario, admin, _, reporte = caso_reporte
    hv = headers_de(voluntario)
    _cerrar(cliente, hv, _tomar_reporte(cliente, hv, reporte.id)["id"], "finalizada")

    otro = crear_usuario(V)
    otro.organizacion_id = voluntario.organizacion_id
    db.flush()
    r = cliente.post(f"/reportes/{reporte.id}/asignar", headers=headers_de(otro))
    assert r.status_code == 409 and r.json()["codigo"] == "REPORTE_NO_ASIGNABLE"
    r = cliente.patch(f"/reportes/{reporte.id}/rechazar", headers=headers_de(admin))
    assert r.status_code == 409


def test_mientras_lo_atiende_el_panel_ve_al_voluntario(cliente, headers_de, caso_reporte):
    voluntario, admin, ciudadano, reporte = caso_reporte
    _tomar_reporte(cliente, headers_de(voluntario), reporte.id)

    item = next(r for r in cliente.get("/reportes", headers=headers_de(admin)).json()["items"] if r["id"] == str(reporte.id))
    assert item["estado"] == "verificado"
    assert item["atencion"]["estado"] == "activa" and item["atencion"]["hasta"] is None
    # El ciudadano autor ve su reporte, pero no quién lo atiende
    assert cliente.get(f"/reportes/{reporte.id}", headers=headers_de(ciudadano)).json()["atencion"] is None


# --- solicitudes ---


def test_solicitud_atendida_trae_quien_la_atendio(cliente, db, crear_usuario, headers_de):
    voluntario = crear_usuario(V)
    ciudadano = crear_usuario(C)
    hc = headers_de(ciudadano)
    sid = cliente.post(
        "/solicitudes-ayuda",
        json={"descripcion": "Necesito agua", "tipo": "alimentaria", "ubicacion": {"lat": PUNTO[0], "lng": PUNTO[1]}},
        headers=hc,
    ).json()["id"]
    solicitud = db.get(SolicitudAyuda, UUID(sid))
    solicitud.organizacion_manual_id = voluntario.organizacion_id
    db.flush()

    hv = headers_de(voluntario)
    asignacion = cliente.post(f"/solicitudes-ayuda/{sid}/asignar", headers=hv).json()
    _cerrar(cliente, hv, asignacion["id"], "finalizada")

    vista = cliente.get(f"/solicitudes-ayuda/{sid}", headers=headers_de(crear_usuario(S))).json()
    assert vista["estado"] == "atendida"
    assert vista["atencion"]["voluntario"]["id"] == str(voluntario.id)
    assert vista["atencion"]["estado"] == "finalizada"
    # El ciudadano no recibe el dato del voluntario
    assert cliente.get(f"/solicitudes-ayuda/{sid}", headers=hc).json()["atencion"] is None
