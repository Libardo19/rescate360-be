"""Mapa en vivo: capas, privacidad por rol, radio y polling con `desde`."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.models.enums import EstadoReporte, EstadoSolicitud, RolUsuario
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.utils.geo import punto_desde_latlng

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
VALLEDUPAR = (10.463123, -73.253217)
BOGOTA = (4.711, -74.0721)


def _solicitud(cliente, headers, lat_lng=VALLEDUPAR, tipo="medica") -> str:
    cuerpo = {"descripcion": "Abuela sin medicamentos", "tipo": tipo, "ubicacion": {"lat": lat_lng[0], "lng": lat_lng[1]}}
    r = cliente.post("/solicitudes-ayuda", json=cuerpo, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _reporte(db, usuario, *, estado=EstadoReporte.PENDIENTE, organizacion_id=None, lat_lng=VALLEDUPAR) -> Reporte:
    reporte = Reporte(
        usuario_id=usuario.id,
        tipo="incendio",
        descripcion="Humo en el barrio",
        ubicacion=punto_desde_latlng(*lat_lng),
        estado=estado,
        organizacion_objetivo_id=organizacion_id,
    )
    db.add(reporte)
    db.flush()
    return reporte


def _enrutar(db, solicitud_id: str, organizacion_id) -> None:
    solicitud = db.get(SolicitudAyuda, UUID(solicitud_id))
    solicitud.organizacion_manual_id = organizacion_id
    db.flush()


def _mapa(cliente, headers, **params) -> dict:
    r = cliente.get("/mapa", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _por_id(respuesta: dict) -> dict[str, dict]:
    return {p["id"]: p for p in respuesta["puntos"]}


# --- privacidad por rol ---


def test_ciudadano_ve_lo_suyo_exacto_y_lo_ajeno_aproximado(cliente, crear_usuario, headers_de):
    yo, vecino = crear_usuario(C), crear_usuario(C)
    mia = _solicitud(cliente, headers_de(yo))
    ajena = _solicitud(cliente, headers_de(vecino))

    puntos = _por_id(_mapa(cliente, headers_de(yo)))
    assert puntos[mia]["propio"] and not puntos[mia]["aproximada"]
    assert puntos[mia]["lat"] == pytest.approx(VALLEDUPAR[0])
    assert puntos[mia]["detalle"] == "Abuela sin medicamentos"

    otro = puntos[ajena]
    assert not otro["propio"] and otro["aproximada"]
    assert otro["lat"] != pytest.approx(VALLEDUPAR[0], abs=1e-6)
    assert abs(otro["lat"] - VALLEDUPAR[0]) < 0.002 and abs(otro["lng"] - VALLEDUPAR[1]) < 0.002
    assert "Abuela" not in otro["detalle"]
    assert otro["capa"] == "solicitud" and otro["titulo"] == "Ayuda médica" and otro["activo"]


def test_la_organizacion_ve_exacto_lo_que_tiene_enrutado(cliente, db, crear_usuario, headers_de):
    admin = crear_usuario(A)
    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    enrutada = _solicitud(cliente, headers_de(crear_usuario(C)))
    sin_enrutar = _solicitud(cliente, headers_de(crear_usuario(C)))
    _enrutar(db, enrutada, admin.organizacion_id)

    for usuario in (admin, voluntario):
        puntos = _por_id(_mapa(cliente, headers_de(usuario)))
        assert puntos[enrutada]["propio"] and not puntos[enrutada]["aproximada"]
        assert puntos[sin_enrutar]["aproximada"]


def test_super_admin_ve_todo_exacto(cliente, crear_usuario, headers_de):
    solicitud = _solicitud(cliente, headers_de(crear_usuario(C)))
    punto = _por_id(_mapa(cliente, headers_de(crear_usuario(S))))[solicitud]
    assert punto["propio"] and not punto["aproximada"]


def test_sos_sale_como_sos_con_prioridad_critica(cliente, crear_usuario, headers_de):
    yo = crear_usuario(C)
    r = cliente.post(
        "/solicitudes-ayuda/sos", json={"ubicacion": {"lat": VALLEDUPAR[0], "lng": VALLEDUPAR[1]}}, headers=headers_de(yo)
    )
    punto = _por_id(_mapa(cliente, headers_de(yo)))[r.json()["id"]]
    assert punto["titulo"] == "SOS" and punto["prioridad"] == "critica"


def test_reportes_sin_verificar_solo_los_ven_su_autor_su_organizacion_y_el_super_admin(
    cliente, db, crear_usuario, headers_de
):
    autor = crear_usuario(C)
    admin = crear_usuario(A)
    pendiente = _reporte(db, autor, organizacion_id=admin.organizacion_id)
    verificado = _reporte(db, autor, estado=EstadoReporte.VERIFICADO)
    rechazado = _reporte(db, autor, estado=EstadoReporte.RECHAZADO)

    def ids(usuario):
        return set(_por_id(_mapa(cliente, headers_de(usuario), capas="reportes")))

    p, v, r = str(pendiente.id), str(verificado.id), str(rechazado.id)
    assert ids(crear_usuario(C)) == {v}  # otro ciudadano: solo lo verificado
    assert ids(crear_usuario(A)) == {v}  # admin de otra organización
    assert ids(autor) == {p, v}
    assert ids(admin) == {p, v}
    assert ids(crear_usuario(S)) == {p, v}  # el rechazado ya no está abierto


# --- filtros ---


def test_radio_deja_por_fuera_lo_lejano(cliente, crear_usuario, headers_de):
    yo = crear_usuario(C)
    cerca = _solicitud(cliente, headers_de(yo))
    lejos = _solicitud(cliente, headers_de(yo), lat_lng=BOGOTA)

    con_radio = _por_id(_mapa(cliente, headers_de(yo), lat=VALLEDUPAR[0], lng=VALLEDUPAR[1], radio_m=3000))
    assert cerca in con_radio and lejos not in con_radio
    sin_radio = _por_id(_mapa(cliente, headers_de(yo)))
    assert {cerca, lejos} <= set(sin_radio)


def test_capas_pedidas(cliente, db, crear_usuario, headers_de):
    yo = crear_usuario(C)
    _solicitud(cliente, headers_de(yo))
    _reporte(db, yo)
    capas = {p["capa"] for p in _mapa(cliente, headers_de(yo), capas="solicitudes")["puntos"]}
    assert capas == {"solicitud"}
    capas = {p["capa"] for p in _mapa(cliente, headers_de(yo))["puntos"]}
    assert capas == {"solicitud", "reporte"}


def test_polling_con_desde_trae_solo_lo_que_cambio_incluido_lo_cerrado(cliente, db, crear_usuario, headers_de):
    yo = crear_usuario(C)
    vieja, cerrada, nueva = (_solicitud(cliente, headers_de(yo)) for _ in range(3))
    hace_una_hora = datetime.now(UTC) - timedelta(hours=1)
    for solicitud_id, estado in ((vieja, EstadoSolicitud.PENDIENTE), (cerrada, EstadoSolicitud.CANCELADA)):
        fila = db.get(SolicitudAyuda, UUID(solicitud_id))
        fila.estado = estado
        fila.actualizado_en = hace_una_hora if solicitud_id == vieja else datetime.now(UTC)
    db.flush()

    # Mapa completo: solo lo abierto
    completo = _mapa(cliente, headers_de(yo))
    assert set(_por_id(completo)) >= {vieja, nueva} and cerrada not in _por_id(completo)
    assert completo["generado_en"]

    # Polling: solo lo que cambió en los últimos 10 minutos, también lo cerrado
    desde = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    cambios = _por_id(_mapa(cliente, headers_de(yo), desde=desde))
    assert vieja not in cambios
    assert cambios[cerrada]["activo"] is False
    assert cambios[nueva]["activo"] is True


@pytest.mark.parametrize(
    ("params", "codigo"),
    [({"capas": "solicitudes,volcanes"}, "CAPA_INVALIDA"), ({"lat": 10.4}, "UBICACION_INCOMPLETA")],
)
def test_consultas_invalidas(cliente, crear_usuario, headers_de, params, codigo):
    r = cliente.get("/mapa", params=params, headers=headers_de(crear_usuario(C)))
    assert r.status_code == 422 and r.json()["codigo"] == codigo


def test_capas_futuras_responden_vacio(cliente, crear_usuario, headers_de):
    assert _mapa(cliente, headers_de(crear_usuario(C)), capas="centros,zonas,alertas")["puntos"] == []


def test_mapa_exige_sesion(cliente):
    assert cliente.get("/mapa").status_code == 401
