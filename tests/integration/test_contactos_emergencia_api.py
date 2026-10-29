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


# --- SMS del SOS ---


class _SesionDePrueba:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, nombre):
        return getattr(self._db, nombre)

    def close(self):
        pass


@pytest.fixture
def sms(db, monkeypatch):
    from app.jobs.eventos import enviar_sms_respaldo as job

    enviados: list[tuple[str, str]] = []
    monkeypatch.setattr(job, "SessionLocal", lambda: _SesionDePrueba(db))
    monkeypatch.setattr(job, "enviar_sms", lambda telefono, texto: enviados.append((telefono, texto)))
    return job, enviados


def test_el_sos_encola_el_sms_y_llega_a_cada_contacto(cliente, crear_usuario, headers_de, encolados, sms):
    job, enviados = sms
    usuario = crear_usuario()
    h = headers_de(usuario)
    _crear(cliente, h)
    _crear(cliente, h, nombre="Ana", telefono="+573109876543")
    sid = cliente.post("/solicitudes-ayuda/sos", json={"ubicacion": {"lat": 10.4631, "lng": -73.2532}}, headers=h).json()["id"]
    assert ("enviar_sms_respaldo", (sid,)) in encolados

    resultado = job.enviar_sms_respaldo.run(sid)
    assert resultado["enviados"] == 2
    assert [t for t, _ in enviados] == ["+573001234567", "+573109876543"]
    assert usuario.nombre in enviados[0][1] and "10.46310,-73.25320" in enviados[0][1] and "123" in enviados[0][1]


def test_sin_contactos_o_sin_sos_no_se_envia_nada(cliente, crear_usuario, headers_de, encolados, sms):
    job, enviados = sms
    h = headers_de(crear_usuario())
    sid = cliente.post("/solicitudes-ayuda/sos", json={"ubicacion": {"lat": 10.4, "lng": -73.2}}, headers=h).json()["id"]
    assert job.enviar_sms_respaldo.run(sid)["status"] == "sin_contactos"

    _crear(cliente, h)
    normal = cliente.post(
        "/solicitudes-ayuda",
        json={"descripcion": "Necesito agua", "tipo": "alimentaria", "ubicacion": {"lat": 10.4, "lng": -73.2}},
        headers=h,
    ).json()["id"]
    assert not any(n == "enviar_sms_respaldo" and a == (normal,) for n, a in encolados)
    assert job.enviar_sms_respaldo.run(normal)["status"] == "no_aplica"
    assert enviados == []


def test_un_contacto_que_falla_no_frena_a_los_demas(cliente, crear_usuario, headers_de, encolados, sms, monkeypatch):
    from app.integrations.twilio_client import ErrorSMS

    job, _ = sms
    llegaron = []

    def _enviar(telefono, texto):
        if telefono == "+573001234567":
            raise ErrorSMS("número inválido")
        llegaron.append(telefono)

    monkeypatch.setattr(job, "enviar_sms", _enviar)
    h = headers_de(crear_usuario())
    _crear(cliente, h)
    _crear(cliente, h, nombre="Ana", telefono="+573109876543")
    sid = cliente.post("/solicitudes-ayuda/sos", json={"ubicacion": {"lat": 10.4, "lng": -73.2}}, headers=h).json()["id"]
    assert job.enviar_sms_respaldo.run(sid)["enviados"] == 1
    assert llegaron == ["+573109876543"]
