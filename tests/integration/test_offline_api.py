"""Modo sin conexión: llave, firma, sync propio, relevo de terceros, deduplicación y procesamiento."""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.jobs.eventos import procesar_lote_offline as job
from app.models.auditoria import Auditoria
from app.models.check_in import CheckIn
from app.models.cola_alerta_offline import ColaAlertaOffline
from app.models.enums import EstadoCheckIn, MetodoEnvio, OrigenSolicitud
from app.models.solicitud_ayuda import SolicitudAyuda
from app.services import offline_service

VALLEDUPAR = (10.4631, -73.2532)


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
    monkeypatch.setattr(job, "SessionLocal", lambda: _SesionDePrueba(db))
    monkeypatch.setattr(offline_service, "enviar_sms", lambda telefono, texto: sms.append((telefono, texto)))
    return sms


def _llave(cliente, headers) -> str:
    r = cliente.get("/usuarios/me/llave-offline", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["llave"]


def _mensaje(usuario, llave, tipo="sos", saltos=0, generado=None, **cambios) -> dict:
    """Arma el mensaje como lo firma la app."""
    generado = generado or datetime.now(UTC).replace(microsecond=0)
    m = {
        "uuid_origen": str(uuid.uuid4()),
        "usuario_id": str(usuario.id),
        "tipo": tipo,
        "lat": VALLEDUPAR[0],
        "lng": VALLEDUPAR[1],
        "generado_en": generado.isoformat().replace("+00:00", "Z"),
        "saltos": saltos,
    }
    m.update(cambios)
    texto = f"{m['uuid_origen']}|{m['usuario_id']}|{m['tipo']}|{m['lat']:.6f}|{m['lng']:.6f}|{m['generado_en']}"
    if r := m.get("reporte"):
        texto += f"|{r['tipo']}|{r['descripcion']}|{r.get('direccion') or ''}"
    m["firma"] = hmac.new(llave.encode(), texto.encode(), hashlib.sha256).hexdigest()
    return m


def _procesar(encolados):
    ids = next(args[0] for nombre, args in reversed(encolados) if nombre == "procesar_lote_offline")
    return job.procesar_lote_offline.run(ids)


# --- llave ---


def test_la_llave_es_estable_y_no_sale_en_la_auditoria(cliente, db, crear_usuario, headers_de):
    usuario = crear_usuario()
    h = headers_de(usuario)
    llave = _llave(cliente, h)
    assert len(llave) == 64 and _llave(cliente, h) == llave
    historia = db.scalars(select(Auditoria).where(Auditoria.tabla == "usuarios", Auditoria.registro_id == usuario.id))
    assert all("llave_offline" not in (f.datos_nuevos or {}) for f in historia)
    assert "llave" not in cliente.get("/usuarios/me", headers=h).text


# --- relevo ---


def test_relevo_de_un_sos_ajeno_crea_el_sos_mesh_y_el_sms(cliente, db, crear_usuario, headers_de, entorno, encolados):
    autor = crear_usuario()
    mensaje = _mensaje(autor, _llave(cliente, headers_de(autor)), saltos=2)
    portador = headers_de(crear_usuario())  # el teléfono con internet que lo trae

    r = cliente.post("/offline/relevo", json={"mensajes": [mensaje]}, headers=portador)
    assert r.status_code == 202, r.text
    assert r.json() == {"aceptados": 1, "duplicados": 0, "rechazados": []}

    resultado = _procesar(encolados)
    assert resultado["resultados"] == {mensaje["uuid_origen"]: "sos_creado"}
    solicitud = db.scalar(select(SolicitudAyuda).where(SolicitudAyuda.usuario_id == autor.id))
    assert solicitud.origen == OrigenSolicitud.MESH
    assert ("enviar_sms_respaldo", (str(solicitud.id),)) in encolados
    fila = db.scalar(select(ColaAlertaOffline).where(ColaAlertaOffline.uuid_origen == UUID(mensaje["uuid_origen"])))
    assert fila.metodo_envio == MetodoEnvio.MESH and fila.saltos == 2 and fila.sincronizado and fila.subido_por


def test_el_mismo_mensaje_por_dos_telefonos_se_procesa_una_vez(cliente, db, crear_usuario, headers_de, entorno, encolados):
    autor = crear_usuario()
    mensaje = _mensaje(autor, _llave(cliente, headers_de(autor)), saltos=1)
    cliente.post("/offline/relevo", json={"mensajes": [mensaje]}, headers=headers_de(crear_usuario()))
    _procesar(encolados)
    r = cliente.post("/offline/relevo", json={"mensajes": [{**mensaje, "saltos": 3}]}, headers=headers_de(crear_usuario()))
    assert r.json() == {"aceptados": 0, "duplicados": 1, "rechazados": []}
    assert len(db.scalars(select(SolicitudAyuda).where(SolicitudAyuda.usuario_id == autor.id)).all()) == 1


@pytest.mark.parametrize(
    ("cambio", "motivo"),
    [
        ({"lat": 4.71}, "FIRMA_INVALIDA"),  # un intermediario movió la ubicación
        ({"tipo": "a_salvo"}, "FIRMA_INVALIDA"),
        ({"saltos": 9}, "DEMASIADOS_SALTOS"),
    ],
)
def test_relevo_rechaza_lo_alterado(cliente, crear_usuario, headers_de, cambio, motivo):
    autor = crear_usuario()
    mensaje = {**_mensaje(autor, _llave(cliente, headers_de(autor))), **cambio}
    r = cliente.post("/offline/relevo", json={"mensajes": [mensaje]}, headers=headers_de(crear_usuario()))
    assert r.json()["rechazados"] == [{"uuid_origen": mensaje["uuid_origen"], "motivo": motivo}]


def test_relevo_rechaza_vencidos_y_autores_sin_llave(cliente, crear_usuario, headers_de):
    autor = crear_usuario()
    llave = _llave(cliente, headers_de(autor))
    viejo = _mensaje(autor, llave, generado=datetime.now(UTC) - timedelta(hours=25))
    futuro = _mensaje(autor, llave, generado=datetime.now(UTC) + timedelta(hours=1))
    sin_llave = _mensaje(crear_usuario(), "a" * 64)
    r = cliente.post("/offline/relevo", json={"mensajes": [viejo, futuro, sin_llave]}, headers=headers_de(crear_usuario()))
    assert [x["motivo"] for x in r.json()["rechazados"]] == ["MENSAJE_VENCIDO", "MENSAJE_VENCIDO", "USUARIO_DESCONOCIDO"]


# --- sync propio ---


def test_sync_solo_acepta_lo_propio(cliente, crear_usuario, headers_de, entorno, encolados):
    yo, otro = crear_usuario(), crear_usuario()
    h = headers_de(yo)
    propio = _mensaje(yo, _llave(cliente, h))
    ajeno = _mensaje(otro, _llave(cliente, headers_de(otro)))
    r = cliente.post("/offline/sync", json={"mensajes": [propio, ajeno]}, headers=h)
    assert r.status_code == 202
    assert r.json()["aceptados"] == 1 and r.json()["rechazados"][0]["motivo"] == "NO_ES_TUYO"


def test_a_salvo_sin_conexion_cierra_el_check_in(cliente, db, crear_usuario, headers_de, entorno, encolados):
    usuario = crear_usuario()
    h = headers_de(usuario)
    check_in = cliente.post("/check-ins", json={}, headers=h).json()
    cliente.post("/offline/sync", json={"mensajes": [_mensaje(usuario, _llave(cliente, h), tipo="a_salvo")]}, headers=h)
    _procesar(encolados)
    assert db.get(CheckIn, UUID(check_in["id"])).estado == EstadoCheckIn.A_SALVO


def test_sin_respuesta_sin_conexion_avisa_a_los_contactos(cliente, db, crear_usuario, headers_de, entorno, encolados):
    sms = entorno
    usuario = crear_usuario()
    h = headers_de(usuario)
    cliente.post("/usuarios/me/contactos-emergencia", json={"nombre": "Ana", "telefono": "3001234567"}, headers=h)
    check_in = cliente.post("/check-ins", json={}, headers=h).json()
    mensaje = _mensaje(usuario, _llave(cliente, h), tipo="sin_respuesta", saltos=1)
    cliente.post("/offline/relevo", json={"mensajes": [mensaje]}, headers=headers_de(crear_usuario()))
    assert _procesar(encolados)["resultados"][mensaje["uuid_origen"]] == "contactos_avisados"
    assert db.get(CheckIn, UUID(check_in["id"])).estado == EstadoCheckIn.SIN_RESPUESTA
    assert sms[0][0] == "+573001234567" and "10.46310,-73.25320" in sms[0][1]


# --- reporte de incidente sin conexión ---

REPORTE = {"tipo": "Inundación", "descripcion": "El caño se desbordó en la calle 12", "direccion": "Calle 12 #4-30"}


def test_relevo_de_un_reporte_crea_el_reporte_del_autor(cliente, db, crear_usuario, headers_de, entorno, encolados):
    autor = crear_usuario()
    mensaje = _mensaje(autor, _llave(cliente, headers_de(autor)), tipo="reporte", saltos=1, reporte=REPORTE)

    r = cliente.post("/offline/relevo", json={"mensajes": [mensaje]}, headers=headers_de(crear_usuario()))
    assert r.json() == {"aceptados": 1, "duplicados": 0, "rechazados": []}
    assert _procesar(encolados)["resultados"] == {mensaje["uuid_origen"]: "reporte_creado"}

    reportes = cliente.get("/reportes", headers=headers_de(autor)).json()["items"]
    assert len(reportes) == 1
    assert reportes[0]["tipo"] == "inundacion" and reportes[0]["descripcion"] == REPORTE["descripcion"]
    assert reportes[0]["ubicacion"] == {"lat": VALLEDUPAR[0], "lng": VALLEDUPAR[1]}
    assert ("clasificar_reporte_ia", (reportes[0]["id"],)) in encolados


def test_un_intermediario_no_puede_cambiar_el_texto_del_reporte(cliente, crear_usuario, headers_de):
    autor = crear_usuario()
    mensaje = _mensaje(autor, _llave(cliente, headers_de(autor)), tipo="reporte", reporte=REPORTE)
    mensaje["reporte"] = {**REPORTE, "descripcion": "Falsa alarma, no pasa nada"}
    r = cliente.post("/offline/relevo", json={"mensajes": [mensaje]}, headers=headers_de(crear_usuario()))
    assert r.json()["rechazados"][0]["motivo"] == "FIRMA_INVALIDA"


def test_reporte_sin_datos_o_datos_en_otro_tipo_es_invalido(cliente, crear_usuario, headers_de):
    usuario = crear_usuario()
    h = headers_de(usuario)
    llave = _llave(cliente, h)
    for mensaje in (_mensaje(usuario, llave, tipo="reporte"), _mensaje(usuario, llave, tipo="sos", reporte=REPORTE)):
        assert cliente.post("/offline/sync", json={"mensajes": [mensaje]}, headers=h).status_code == 422


def test_lote_vacio_o_muy_grande(cliente, crear_usuario, headers_de):
    h = headers_de(crear_usuario())
    assert cliente.post("/offline/sync", json={"mensajes": []}, headers=h).status_code == 422
    assert cliente.post("/offline/relevo", json={"mensajes": []}).status_code == 401
