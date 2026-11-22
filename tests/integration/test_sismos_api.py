"""Sismos y "¿Estás bien?": feed, alerta automática, simulacro, check-ins, vencimiento y mapa."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.integrations import sismos_client
from app.jobs.programados import sincronizar_sismos as job_sismos
from app.jobs.programados import vencer_check_ins as job_vencer
from app.models.alerta import Alerta
from app.models.check_in import CheckIn
from app.models.enums import EstadoCheckIn, OrigenSolicitud, RolUsuario
from app.models.evento_sismico import EventoSismico
from app.models.solicitud_ayuda import SolicitudAyuda
from app.services import sismos_service
from app.utils.geo import punto_desde_latlng

C, A, S = RolUsuario.CIUDADANO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
VALLEDUPAR = (10.4631, -73.2532)


def _feature(id_, mag, lat, lng, prof=12.0, minutos_atras=3):
    return {
        "id": id_,
        "properties": {
            "mag": mag,
            "place": f"10 km de prueba ({id_})",
            "time": int((datetime.now(UTC) - timedelta(minutes=minutos_atras)).timestamp() * 1000),
        },
        "geometry": {"coordinates": [lng, lat, prof]},
    }


class _SesionDePrueba:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, nombre):
        return getattr(self._db, nombre)

    def close(self):
        pass


@pytest.fixture
def entorno(db, monkeypatch, encolados):
    sms: list[tuple[str, str]] = []
    for job in (job_sismos, job_vencer):
        monkeypatch.setattr(job, "SessionLocal", lambda: _SesionDePrueba(db))
    monkeypatch.setattr(job_vencer, "enviar_sms", lambda telefono, texto: sms.append((telefono, texto)))
    return sms


def _ubicar(db, usuario, lat, lng):
    usuario.ubicacion_actual = punto_desde_latlng(lat, lng)
    usuario.ubicacion_actualizada_en = datetime.now(UTC)
    db.flush()


# --- feed ---


def test_parsea_todo_el_mundo_con_magnitud_valida():
    sismos = sismos_client.parsear(
        {
            "features": [
                _feature("co1", 4.8, 7.1, -73.1),  # Santander
                _feature("cl1", 6.0, -33.4, -70.6),  # Chile: también se guarda (sale en el mapa)
                _feature("micro", -0.4, 38.8, -122.8),  # magnitud negativa: se descarta
                {**_feature("sin", 3.0, 7.0, -73.0), "properties": {"mag": None, "place": "x", "time": 0}},
            ]
        }
    )
    assert [s.id_externo for s in sismos] == ["usgs:co1", "usgs:cl1"]
    assert sismos[0].magnitud == 4.8 and sismos[0].profundidad_km == 12.0
    assert sismos_client.en_colombia(7.1, -73.1) and not sismos_client.en_colombia(-33.4, -70.6)


def test_radio_y_nivel_crecen_con_la_magnitud():
    assert sismos_service.radio_afectacion(4.5) == 10_000
    assert sismos_service.radio_afectacion(5.5) == 20_000
    assert sismos_service.radio_afectacion(9.5) == 300_000
    assert [sismos_service.nivel_por_magnitud(m).value for m in (4.6, 5.3, 6.4)] == ["bajo", "medio", "alto"]


def test_sincronizar_es_idempotente_y_alerta_solo_los_fuertes(db, crear_usuario, entorno, encolados, monkeypatch):
    cerca, lejos = crear_usuario(C), crear_usuario(C)
    _ubicar(db, cerca, 10.47, -73.25)
    _ubicar(db, lejos, 4.71, -74.07)  # Bogotá
    feed = [
        sismos_client.parsear({"features": [_feature("fuerte", 5.0, *VALLEDUPAR)]})[0],
        sismos_client.parsear({"features": [_feature("leve", 3.1, 7.0, -73.0)]})[0],
    ]
    monkeypatch.setattr(sismos_client, "obtener_recientes", lambda url=None: feed)

    assert job_sismos.sincronizar_sismos.run() == {"status": "ok", "nuevos": 2, "alertados": 1}
    assert job_sismos.sincronizar_sismos.run() == {"status": "ok", "nuevos": 0, "alertados": 0}

    fuerte = db.scalar(select(EventoSismico).where(EventoSismico.id_externo == "usgs:fuerte"))
    alerta = db.get(Alerta, fuerte.alerta_id)
    assert alerta.origen == "sismo" and alerta.creado_por is None and alerta.radio_m == fuerte.radio_afectacion_m
    assert ("notificar_alerta_zona", (str(alerta.id),)) in encolados

    check_ins = db.scalars(select(CheckIn).where(CheckIn.evento_sismico_id == fuerte.id)).all()
    assert [c.usuario_id for c in check_ins] == [cerca.id]
    assert check_ins[0].estado == EstadoCheckIn.PENDIENTE


def test_feed_caido_no_rompe(entorno, monkeypatch):
    def _falla(*args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr(sismos_client.urllib.request, "urlopen", _falla)
    assert sismos_client.obtener_recientes() == []
    assert job_sismos.sincronizar_sismos.run()["nuevos"] == 0


# --- endpoints ---


def test_simulacro_y_detalle_con_distancia(cliente, db, crear_usuario, headers_de, entorno):
    ciudadano = crear_usuario(C)
    _ubicar(db, ciudadano, 10.47, -73.25)
    r = cliente.post("/sismos/simular", json={"magnitud": 5.5}, headers=headers_de(crear_usuario(S)))
    assert r.status_code == 201, r.text
    sismo = r.json()
    assert sismo["fuente"] == "simulado" and sismo["alerta_id"] and sismo["radio_afectacion_m"] == 20_000
    assert "no es una alerta temprana oficial" in sismo["aviso"]

    detalle = cliente.get(f"/sismos/{sismo['id']}", headers=headers_de(ciudadano)).json()
    assert 0 < detalle["distancia_m"] < 2_000
    lista = cliente.get("/sismos", params={"magnitud_min": 5}, headers=headers_de(ciudadano)).json()
    assert sismo["id"] in [s["id"] for s in lista["items"]]
    # El ciudadano cercano recibió su "¿Estás bien?"
    pendiente = cliente.get("/check-ins/pendiente", headers=headers_de(ciudadano)).json()
    assert pendiente["evento_sismico_id"] == sismo["id"] and pendiente["motivo"] == "sismo"


def test_simulacro_solo_super_admin_y_en_local(cliente, crear_usuario, headers_de, monkeypatch):
    assert cliente.post("/sismos/simular", headers=headers_de(crear_usuario(A))).status_code == 403
    monkeypatch.setattr(get_settings(), "app_env", "production")
    r = cliente.post("/sismos/simular", headers=headers_de(crear_usuario(S)))
    assert r.status_code == 403 and r.json()["codigo"] == "SIMULACRO_NO_DISPONIBLE"


# --- check-ins ---


def test_a_salvo_cierra_el_check_in(cliente, crear_usuario, headers_de):
    h = headers_de(crear_usuario(C))
    assert cliente.get("/check-ins/pendiente", headers=h).json() is None
    check_in = cliente.post("/check-ins", json={"ubicacion": {"lat": 10.46, "lng": -73.25}}, headers=h).json()
    assert check_in["motivo"] == "manual" and check_in["estado"] == "pendiente"
    assert cliente.post("/check-ins", json={}, headers=h).status_code == 409

    r = cliente.post(f"/check-ins/{check_in['id']}/responder", json={"estado": "a_salvo"}, headers=h)
    assert r.status_code == 200 and r.json()["estado"] == "a_salvo" and r.json()["respondido_en"]
    assert cliente.post(f"/check-ins/{check_in['id']}/responder", json={"estado": "a_salvo"}, headers=h).status_code == 409


def test_necesito_ayuda_crea_un_sos(cliente, db, crear_usuario, headers_de, encolados):
    h = headers_de(crear_usuario(C))
    check_in = cliente.post("/check-ins", json={}, headers=h).json()
    r = cliente.post(f"/check-ins/{check_in['id']}/responder", json={"estado": "necesito_ayuda"}, headers=h)
    assert r.status_code == 422 and r.json()["codigo"] == "UBICACION_REQUERIDA"

    r = cliente.post(
        f"/check-ins/{check_in['id']}/responder",
        json={"estado": "necesito_ayuda", "ubicacion": {"lat": 10.46, "lng": -73.25}},
        headers=h,
    )
    assert r.status_code == 200, r.text
    solicitud = db.get(SolicitudAyuda, UUID(r.json()["solicitud_id"]))
    assert solicitud.origen == OrigenSolicitud.SOS
    assert ("enviar_sms_respaldo", (str(solicitud.id),)) in encolados


def test_no_se_responde_el_de_otro(cliente, crear_usuario, headers_de):
    check_in = cliente.post("/check-ins", json={}, headers=headers_de(crear_usuario(C))).json()
    r = cliente.post(
        f"/check-ins/{check_in['id']}/responder", json={"estado": "a_salvo"}, headers=headers_de(crear_usuario(C))
    )
    assert r.status_code == 404


def test_vencido_queda_sin_respuesta_y_avisa_a_los_contactos(cliente, db, crear_usuario, headers_de, entorno):
    sms = entorno
    usuario = crear_usuario(C)
    h = headers_de(usuario)
    cliente.post("/usuarios/me/contactos-emergencia", json={"nombre": "Ana", "telefono": "3001234567"}, headers=h)
    check_in = cliente.post("/check-ins", json={"ubicacion": {"lat": 10.46, "lng": -73.25}}, headers=h).json()
    fila = db.get(CheckIn, UUID(check_in["id"]))
    fila.vence_en = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()

    assert job_vencer.vencer_check_ins.run() == {"status": "ok", "vencidos": 1, "sms": 1}
    db.refresh(fila)
    assert fila.estado == EstadoCheckIn.SIN_RESPUESTA
    assert sms[0][0] == "+573001234567" and "10.46000,-73.25000" in sms[0][1] and usuario.nombre in sms[0][1]


def test_panel_ve_el_resumen_del_sismo(cliente, db, crear_usuario, headers_de, entorno):
    a_salvo, sin_responder = crear_usuario(C), crear_usuario(C)
    for u in (a_salvo, sin_responder):
        _ubicar(db, u, 10.47, -73.25)
    sismo = cliente.post("/sismos/simular", json={}, headers=headers_de(crear_usuario(S))).json()
    mio = cliente.get("/check-ins/pendiente", headers=headers_de(a_salvo)).json()
    cliente.post(f"/check-ins/{mio['id']}/responder", json={"estado": "a_salvo"}, headers=headers_de(a_salvo))

    admin = headers_de(crear_usuario(A))
    r = cliente.get("/check-ins", params={"evento_sismico_id": sismo["id"]}, headers=admin)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["resumen"] == {"pendiente": 1, "a_salvo": 1, "necesito_ayuda": 0, "sin_respuesta": 0}
    assert datos["personas"][0]["nombre"] == sin_responder.nombre  # los pendientes antes que los a salvo
    assert cliente.get("/check-ins", headers=headers_de(crear_usuario(C))).status_code == 403


# --- mapa ---


def test_capa_de_sismos_en_el_mapa(cliente, crear_usuario, headers_de, entorno):
    sismo = cliente.post("/sismos/simular", json={}, headers=headers_de(crear_usuario(S))).json()
    puntos = cliente.get("/mapa", params={"capas": "sismos,alertas"}, headers=headers_de(crear_usuario(C))).json()["puntos"]
    capas = {p["capa"] for p in puntos if p["id"] in (sismo["id"], sismo["alerta_id"])}
    assert capas == {"sismo", "alerta"}


# --- sismos de todo el mundo ---


def _sincronizar(monkeypatch, *features):
    feed = sismos_client.parsear({"features": list(features)})
    monkeypatch.setattr(sismos_client, "obtener_recientes", lambda url=None: feed)
    return job_sismos.sincronizar_sismos.run()


def test_sismo_fuera_de_colombia_se_muestra_pero_no_alerta(db, crear_usuario, entorno, encolados, monkeypatch):
    assert _sincronizar(monkeypatch, _feature("japon", 7.4, 36.1, 140.1)) == {"status": "ok", "nuevos": 1, "alertados": 0}
    evento = db.scalar(select(EventoSismico).where(EventoSismico.id_externo == "usgs:japon"))
    assert evento.alerta_id is None and not sismos_service.es_local(evento)
    assert not [e for e in encolados if e[0].startswith("notificar_alerta")]


def test_el_feed_del_dia_no_repite_los_ya_registrados(db, entorno, monkeypatch):
    urls: list[str | None] = []
    feed = sismos_client.parsear({"features": [_feature("uno", 2.0, 0.0, 120.0), _feature("dos", 3.0, 1.0, 121.0)]})

    def _obtener(url=None):
        urls.append(url)
        return feed

    monkeypatch.setattr(sismos_client, "obtener_recientes", _obtener)
    assert job_sismos.sincronizar_sismos.run()["nuevos"] == 2
    assert job_sismos.sincronizar_sismos.run(dia=True)["nuevos"] == 0
    assert urls == [None, get_settings().sismos_feed_dia_url]


def test_sismo_moderado_solo_avisa_a_la_zona(db, entorno, encolados, monkeypatch):
    _sincronizar(monkeypatch, _feature("moderado", 5.4, *VALLEDUPAR))
    evento = db.scalar(select(EventoSismico).where(EventoSismico.id_externo == "usgs:moderado"))
    assert ("notificar_alerta_zona", (str(evento.alerta_id),)) in encolados
    assert db.get(Alerta, evento.alerta_id).titulo.startswith("Sismo de magnitud")


def test_lista_por_region_y_mapa_mundial(cliente, db, crear_usuario, headers_de, entorno, monkeypatch):
    _sincronizar(monkeypatch, _feature("col", 3.2, 7.1, -73.1), _feature("chile", 5.1, -33.4, -70.6))
    h = headers_de(crear_usuario(C))

    def _ids(region=None):
        params = {"region": region} if region else {}
        items = cliente.get("/sismos", params=params, headers=h).json()["items"]
        return {s["lugar"].split("(")[1][:-1]: s["en_colombia"] for s in items}

    assert {"col": True, "chile": False}.items() <= _ids().items()
    assert "chile" not in _ids("colombia") and "col" in _ids("colombia")
    assert "col" not in _ids("mundo") and "chile" in _ids("mundo")
    assert cliente.get("/sismos", params={"region": "marte"}, headers=h).status_code == 422

    # El mapa trae los de todo el mundo, sin importar dónde está quien consulta
    puntos = cliente.get(
        "/mapa", params={"capas": "sismos", "lat": 10.46, "lng": -73.25, "radio_m": 5000}, headers=h
    ).json()["puntos"]
    por_lugar = {p["detalle"].split("(")[1][:-1]: p for p in puntos if p["capa"] == "sismo"}
    assert por_lugar["chile"]["estado"] == "mundo" and por_lugar["chile"]["radio_m"] is None
    assert por_lugar["chile"]["magnitud"] == 5.1
    assert por_lugar["col"]["estado"] == "colombia" and por_lugar["col"]["radio_m"] > 0


def test_retencion_borra_los_sismos_lejanos_viejos(db, entorno, monkeypatch):
    from app.jobs.programados import limpiar_datos_retencion as job_retencion

    monkeypatch.setattr(job_retencion, "SessionLocal", lambda: _SesionDePrueba(db))
    _sincronizar(
        monkeypatch,
        _feature("viejo_lejos", 4.0, 0.0, 120.0, minutos_atras=60 * 24 * 10),
        _feature("viejo_col", 3.0, 7.1, -73.1, minutos_atras=60 * 24 * 10),
        _feature("nuevo_lejos", 4.0, 1.0, 121.0),
    )
    assert job_retencion.limpiar_datos_retencion.run()["sismos_mundo"] >= 1
    quedan = set(db.scalars(select(EventoSismico.id_externo)))
    assert "usgs:viejo_lejos" not in quedan and {"usgs:viejo_col", "usgs:nuevo_lejos"} <= quedan
