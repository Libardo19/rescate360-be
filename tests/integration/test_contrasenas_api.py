"""Olvidé mi contraseña (SMS o correo) y cambio de contraseña desde la cuenta."""

import re
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.core.security import verify_password
from app.integrations import correo_client, twilio_client
from app.models.enums import EstadoUsuario, RolUsuario
from tests.conftest import PASSWORD_PRUEBAS

CODIGO = re.compile(r"[A-Z2-9]{4}-[A-Z2-9]{4}")


@pytest.fixture
def enviados(monkeypatch) -> list[tuple[str, str, str]]:
    """Captura los SMS y correos en vez de enviarlos: (canal, destino, texto)."""
    salida: list[tuple[str, str, str]] = []
    monkeypatch.setattr(twilio_client, "enviar_sms", lambda tel, texto: salida.append(("sms", tel, texto)))
    monkeypatch.setattr(
        correo_client, "enviar_correo", lambda para, asunto, texto: salida.append(("correo", para, texto))
    )
    return salida


def _recuperar(cliente, email, canal="sms"):
    return cliente.post("/auth/recuperar", json={"email": email, "canal": canal})


def _restablecer(cliente, email, codigo, password="clave-nueva-123"):
    return cliente.post("/auth/restablecer", json={"email": email, "codigo": codigo, "password": password})


def _con_telefono(db, usuario, telefono="+573001234567"):
    usuario.telefono = telefono
    db.flush()
    return usuario


@pytest.mark.parametrize("canal", ["sms", "correo"])
def test_recupera_por_el_canal_elegido_y_restablece(cliente, db, crear_usuario, enviados, canal):
    usuario = _con_telefono(db, crear_usuario())
    r = _recuperar(cliente, usuario.email.upper(), canal)
    assert r.status_code == 202

    assert len(enviados) == 1
    canal_usado, destino, texto = enviados[0]
    assert canal_usado == canal
    assert destino == (usuario.telefono if canal == "sms" else usuario.email)
    codigo = CODIGO.search(texto).group()

    r = _restablecer(cliente, usuario.email, codigo.lower().replace("-", ""))  # se normaliza
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]
    db.refresh(usuario)
    assert verify_password("clave-nueva-123", usuario.password_hash)
    assert usuario.codigo_recuperacion_hash is None

    # Un solo uso
    assert _restablecer(cliente, usuario.email, codigo).json()["codigo"] == "CODIGO_RECUPERACION_INVALIDO"


def test_responde_igual_si_el_correo_no_existe_o_no_hay_dato(cliente, db, crear_usuario, enviados):
    sin_telefono = crear_usuario()
    bloqueado = crear_usuario(estado=EstadoUsuario.BLOQUEADO)
    esperado = _recuperar(cliente, "nadie@prueba.co").json()

    for email, canal in (
        ("nadie@prueba.co", "correo"),
        (sin_telefono.email, "sms"),  # pide SMS pero no tiene teléfono
        (bloqueado.email, "correo"),
    ):
        r = _recuperar(cliente, email, canal)
        assert r.status_code == 202 and r.json() == esperado
    assert enviados == []


def test_codigo_vencido_o_errado(cliente, db, crear_usuario, enviados):
    usuario = crear_usuario()
    _recuperar(cliente, usuario.email, "correo")
    codigo = CODIGO.search(enviados[0][2]).group()

    assert _restablecer(cliente, usuario.email, "AAAA-AAAA").json()["codigo"] == "CODIGO_RECUPERACION_INVALIDO"
    assert _restablecer(cliente, "otro@prueba.co", codigo).json()["codigo"] == "CODIGO_RECUPERACION_INVALIDO"

    usuario.codigo_recuperacion_vence = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    r = _restablecer(cliente, usuario.email, codigo)
    assert r.status_code == 422 and r.json()["codigo"] == "CODIGO_RECUPERACION_INVALIDO"
    db.refresh(usuario)
    assert verify_password(PASSWORD_PRUEBAS, usuario.password_hash)


def test_pedir_otro_codigo_invalida_el_anterior(cliente, crear_usuario, enviados):
    usuario = crear_usuario()
    _recuperar(cliente, usuario.email, "correo")
    _recuperar(cliente, usuario.email, "correo")
    primero, segundo = (CODIGO.search(t).group() for _, _, t in enviados)
    assert _restablecer(cliente, usuario.email, primero).status_code == 422
    assert _restablecer(cliente, usuario.email, segundo).status_code == 200


def test_si_el_envio_falla_la_respuesta_no_cambia(cliente, crear_usuario, monkeypatch):
    def _falla(*_):
        raise correo_client.ErrorCorreo("SMTP caído")

    monkeypatch.setattr(correo_client, "enviar_correo", _falla)
    r = _recuperar(cliente, crear_usuario().email, "correo")
    assert r.status_code == 202


def test_sin_credenciales_los_clientes_solo_escriben_en_el_log(monkeypatch):
    # La app reconfigura el logging al arrancar, así que se captura el logger de cada cliente
    # Aunque el .env local tenga credenciales reales, esta prueba nunca envía nada
    s = get_settings()
    for campo in ("twilio_account_sid", "twilio_auth_token", "twilio_from_number"):
        monkeypatch.setattr(s, campo, "")
    monkeypatch.setattr(s, "mail_enabled", False)
    registros: list[str] = []
    for modulo in (twilio_client, correo_client):
        monkeypatch.setattr(modulo.logger, "info", lambda msg, *args: registros.append(msg % args))

    twilio_client.enviar_sms("+573001234567", "código ABCD-EFGH")
    correo_client.enviar_correo("a@b.co", "Asunto", "código ABCD-EFGH")
    assert len(registros) == 2 and all("ABCD-EFGH" in r for r in registros)


# --- cambiar la contraseña desde la cuenta ---


def test_cambia_su_contrasena(cliente, db, crear_usuario, headers_de):
    usuario = crear_usuario(RolUsuario.VOLUNTARIO)
    r = cliente.patch(
        "/usuarios/me/password",
        json={"password_actual": PASSWORD_PRUEBAS, "password_nueva": "otra-clave-456"},
        headers=headers_de(usuario),
    )
    assert r.status_code == 204, r.text
    r = cliente.post("/auth/login", json={"email": usuario.email, "password": "otra-clave-456"})
    assert r.status_code == 200


@pytest.mark.parametrize(
    ("actual", "nueva", "codigo"),
    [("no-es-esta", "otra-clave-456", "CONTRASENA_ACTUAL_INVALIDA"), (PASSWORD_PRUEBAS, PASSWORD_PRUEBAS, "CONTRASENA_REPETIDA")],
)
def test_cambio_rechazado(cliente, crear_usuario, headers_de, actual, nueva, codigo):
    r = cliente.patch(
        "/usuarios/me/password",
        json={"password_actual": actual, "password_nueva": nueva},
        headers=headers_de(crear_usuario()),
    )
    assert r.status_code == 422 and r.json()["codigo"] == codigo


def test_cambiar_contrasena_exige_sesion(cliente):
    r = cliente.patch("/usuarios/me/password", json={"password_actual": "x", "password_nueva": "otra-clave-456"})
    assert r.status_code == 401
