"""Clasificador de casos: Gemini (simulado) con cadena de modelos y respaldo por reglas."""

from uuid import uuid4

import httpx
import pytest

from app.core.config import get_settings
from app.integrations import ia_client
from app.models.enums import PrioridadSolicitud as P
from app.schemas.ia_schema import CasoIA, OrganizacionIA
from app.services import clasificador_reglas, ia_service

BOMBEROS = OrganizacionIA(id=uuid4(), nombre="Bomberos Valledupar", tipo="bomberos")
CRUZ_ROJA = OrganizacionIA(id=uuid4(), nombre="Cruz Roja Cesar", tipo="cruz_roja")
POLICIA = OrganizacionIA(id=uuid4(), nombre="Policía Metropolitana", tipo="policia")
DEFENSA = OrganizacionIA(id=uuid4(), nombre="Defensa Civil", tipo="defensa_civil")
ORGS = [BOMBEROS, CRUZ_ROJA, POLICIA, DEFENSA]


def _caso(tipo, descripcion, clase="reporte"):
    return CasoIA(clase=clase, tipo=tipo, descripcion=descripcion)


# --- reglas ---


@pytest.mark.parametrize(
    ("tipo", "descripcion", "prioridad", "organizacion"),
    [
        ("incendio", "Sale humo de una bodega y hay personas adentro", P.CRITICA, BOMBEROS),
        ("medica", "Abuela con dolor en el pecho, posible infarto", P.CRITICA, CRUZ_ROJA),
        ("robo", "Le robaron el celular a un peatón", P.MEDIA, POLICIA),
        ("inundacion", "El arroyo se desbordó y entra a las casas", P.ALTA, DEFENSA),
        ("ropa", "Necesitamos ropa para dos adultos", P.BAJA, CRUZ_ROJA),  # sin ONG activa
        ("incendio", "Quema de basura, ya fue controlada", P.MEDIA, BOMBEROS),
        ("fuga de gas", "Olor fuerte a gas en la esquina", P.ALTA, BOMBEROS),
        ("pelea", "Pelea con arma blanca frente al parque", P.ALTA, POLICIA),
    ],
)
def test_reglas(tipo, descripcion, prioridad, organizacion):
    r = clasificador_reglas.clasificar(_caso(tipo, descripcion), ORGS)
    assert r.prioridad == prioridad, r.razonamiento
    assert r.organizacion_id == (organizacion.id if organizacion else None), r.razonamiento
    assert r.fuente == "reglas" and r.confianza == clasificador_reglas.CONFIANZA_REGLAS
    assert r.razonamiento.startswith("Clasificado por reglas")


def test_reglas_sin_organizaciones_activas():
    r = clasificador_reglas.clasificar(_caso("incendio", "Fuego en la cocina"), [])
    assert r.organizacion_id is None and "ninguna adecuada" in r.razonamiento


# --- Gemini (simulado) ---


@pytest.fixture
def con_clave(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(s, "gemini_model", "modelo-a")
    monkeypatch.setattr(s, "gemini_modelos_respaldo", ["modelo-b"])


def _respuesta(**cambios):
    datos = {"prioridad": "critica", "confianza": 0.92, "razonamiento": "Personas atrapadas en un incendio",
             "organizacion_id": str(BOMBEROS.id), "organizacion_sugerida": "Bomberos Valledupar"}
    return ia_client.IAPrioridadRespuesta.model_validate({**datos, **cambios})


def _http_error(status):
    req = httpx.Request("POST", "http://x")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, request=req))


def test_gemini_clasifica(con_clave, monkeypatch):
    monkeypatch.setattr(ia_client, "_llamar", lambda modelo, prompt: _respuesta())
    r = ia_client.clasificar(_caso("incendio", "Personas atrapadas"), ORGS)
    assert (r.prioridad, r.organizacion_id, r.fuente) == (P.CRITICA, BOMBEROS.id, "gemini:modelo-a")


def test_si_el_modelo_esta_saturado_prueba_el_siguiente(con_clave, monkeypatch):
    usados = []

    def llamar(modelo, prompt):
        usados.append(modelo)
        if modelo == "modelo-a":
            raise _http_error(503)
        return _respuesta()

    monkeypatch.setattr(ia_client, "_llamar", llamar)
    assert ia_client.clasificar(_caso("incendio", "x" * 12), ORGS).fuente == "gemini:modelo-b"
    assert usados == ["modelo-a", "modelo-b"]


def test_organizacion_que_no_esta_en_la_lista_se_ignora(con_clave, monkeypatch):
    monkeypatch.setattr(
        ia_client, "_llamar",
        lambda modelo, prompt: _respuesta(organizacion_id=str(uuid4()), organizacion_sugerida="Inventada S.A."),
    )
    assert ia_client.clasificar(_caso("incendio", "x" * 12), ORGS).organizacion_id is None


def test_organizacion_por_nombre_si_el_id_no_coincide(con_clave, monkeypatch):
    monkeypatch.setattr(
        ia_client, "_llamar",
        lambda modelo, prompt: _respuesta(organizacion_id="no-es-un-id", organizacion_sugerida="cruz roja  cesar"),
    )
    assert ia_client.clasificar(_caso("medica", "x" * 12), ORGS).organizacion_id == CRUZ_ROJA.id


def test_clave_invalida_no_insiste_con_otros_modelos(con_clave, monkeypatch):
    usados = []

    def llamar(modelo, prompt):
        usados.append(modelo)
        raise _http_error(400)

    monkeypatch.setattr(ia_client, "_llamar", llamar)
    with pytest.raises(ia_client.IAClasificacionError):
        ia_client.clasificar(_caso("incendio", "x" * 12), ORGS)
    assert usados == ["modelo-a"]


def test_sin_clave_o_si_gemini_falla_usa_las_reglas(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    r = ia_service.clasificar(_caso("incendio", "Hay personas adentro"), ORGS)
    assert r.fuente == "reglas" and r.prioridad == P.CRITICA


def test_el_prompt_incluye_el_caso_y_las_organizaciones():
    prompt = ia_client.construir_prompt(
        CasoIA(clase="reporte", tipo="fuga de gas", descripcion="Olor a gas", evidencias=2), ORGS
    )
    assert "REPORTE DE INCIDENTE" in prompt and "fuga de gas" in prompt and "evidencias adjuntas: 2" in prompt
    assert str(BOMBEROS.id) in prompt


def test_clave_gemini_via_header_no_en_url(con_clave, monkeypatch):
    cliente_real = httpx.Client

    def responder(request):
        assert request.headers["x-goog-api-key"] == "clave-de-prueba"
        assert "key" not in request.url.params
        assert "clave-de-prueba" not in str(request.url)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": _respuesta().model_dump_json()},
        ]}}]})

    monkeypatch.setattr(ia_client.httpx, "Client", lambda **kwargs: cliente_real(
        transport=httpx.MockTransport(responder), **kwargs,
    ))
    resultado = ia_client._llamar("modelo-a", "Caso de prueba")
    assert resultado.prioridad == P.CRITICA
