"""La IA clasifica solicitudes y reportes: prioridad + organización, con Gemini o con reglas."""

from uuid import UUID

import pytest

from app.core.config import get_settings
from app.integrations import ia_client
from app.jobs.eventos import clasificar_prioridad_ia as job_solicitud
from app.jobs.eventos import clasificar_reporte_ia as job_reporte
from app.models.enums import PrioridadSolicitud, RolUsuario, TipoOrganizacion
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.schemas.ia_schema import ClasificacionIA

C, V, A = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 50


class _SesionDePrueba:
    """El job abre y cierra su propia sesión; en las pruebas usa la de la prueba sin cerrarla."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, nombre):
        return getattr(self._db, nombre)

    def close(self):
        pass


@pytest.fixture(autouse=True)
def entorno(db, monkeypatch, tmp_path):
    monkeypatch.setattr(job_solicitud, "SessionLocal", lambda: _SesionDePrueba(db))
    monkeypatch.setattr(job_reporte, "SessionLocal", lambda: _SesionDePrueba(db))
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")  # por defecto: sin IA → reglas
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))


@pytest.fixture
def organizaciones(crear_organizacion):
    return {
        "bomberos": crear_organizacion("Bomberos Demo", TipoOrganizacion.BOMBEROS),
        "cruz_roja": crear_organizacion("Cruz Roja Demo", TipoOrganizacion.CRUZ_ROJA),
        "policia": crear_organizacion("Policía Demo", TipoOrganizacion.POLICIA),
    }


def _solicitud(cliente, headers, descripcion, tipo="medica"):
    r = cliente.post(
        "/solicitudes-ayuda",
        json={"descripcion": descripcion, "tipo": tipo, "ubicacion": {"lat": 10.46, "lng": -73.25}},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_crear_solicitud_encola_su_clasificacion(cliente, crear_usuario, headers_de, encolados):
    sid = _solicitud(cliente, headers_de(crear_usuario(C)), "Dolor fuerte en el pecho")
    assert ("clasificar_prioridad_ia", (sid,)) in encolados


def test_sin_ia_las_reglas_clasifican_y_la_organizacion_ya_ve_el_caso(
    cliente, db, crear_usuario, headers_de, organizaciones
):
    sid = _solicitud(cliente, headers_de(crear_usuario(C)), "Abuela inconsciente, no responde")
    resultado = job_solicitud.clasificar_prioridad_ia.run(sid)
    assert resultado["status"] == "ok" and resultado["fuente"] == "reglas"

    solicitud = db.get(SolicitudAyuda, UUID(sid))
    assert solicitud.prioridad_ia == PrioridadSolicitud.CRITICA
    assert solicitud.organizacion_objetivo_id == organizaciones["cruz_roja"].id
    assert solicitud.razonamiento_ia.startswith("Clasificado por reglas")

    # El voluntario de esa organización ya la ve y la puede tomar
    voluntario = crear_usuario(V, organizacion=organizaciones["cruz_roja"])
    items = cliente.get("/solicitudes-ayuda", headers=headers_de(voluntario)).json()["items"]
    assert [s["id"] for s in items] == [sid]


def test_con_gemini_se_usa_su_sugerencia(cliente, db, crear_usuario, headers_de, organizaciones, monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "clave-de-prueba")
    monkeypatch.setattr(ia_client, "clasificar", lambda caso, orgs: ClasificacionIA(
        prioridad=PrioridadSolicitud.ALTA, confianza=0.88, razonamiento="Familia sin techo tras la creciente",
        organizacion_id=organizaciones["cruz_roja"].id, fuente="gemini:modelo-de-prueba",
    ))
    sid = _solicitud(cliente, headers_de(crear_usuario(C)), "Familia sin techo", tipo="refugio")
    assert job_solicitud.clasificar_prioridad_ia.run(sid)["fuente"] == "gemini:modelo-de-prueba"
    solicitud = db.get(SolicitudAyuda, UUID(sid))
    assert (solicitud.prioridad_ia, solicitud.confianza_ia) == (PrioridadSolicitud.ALTA, 0.88)


def test_es_idempotente_y_no_pisa_lo_manual(cliente, db, crear_usuario, headers_de, organizaciones):
    sid = _solicitud(cliente, headers_de(crear_usuario(C)), "Necesito medicamentos")
    job_solicitud.clasificar_prioridad_ia.run(sid)
    assert job_solicitud.clasificar_prioridad_ia.run(sid)["status"] == "ya_clasificada"

    # La organización manual del super admin prevalece sobre la de la IA
    solicitud = db.get(SolicitudAyuda, UUID(sid))
    solicitud.organizacion_manual_id = organizaciones["policia"].id
    db.flush()
    admin_policia = crear_usuario(A, organizacion=organizaciones["policia"])
    items = cliente.get("/solicitudes-ayuda", headers=headers_de(admin_policia)).json()["items"]
    assert [s["id"] for s in items] == [sid]


def test_el_sos_sigue_critico_y_se_enruta_a_rescate(cliente, db, crear_usuario, headers_de, organizaciones, encolados):
    r = cliente.post("/solicitudes-ayuda/sos", json={"ubicacion": {"lat": 10.46, "lng": -73.25}},
                     headers=headers_de(crear_usuario(C)))
    sid = r.json()["id"]
    assert ("clasificar_prioridad_ia", (sid,)) in encolados
    job_solicitud.clasificar_prioridad_ia.run(sid)
    solicitud = db.get(SolicitudAyuda, UUID(sid))
    assert solicitud.prioridad_ia == PrioridadSolicitud.CRITICA
    assert solicitud.organizacion_objetivo_id == organizaciones["bomberos"].id
    assert job_solicitud.clasificar_prioridad_ia.run(sid)["status"] == "ya_clasificada"


def test_reporte_se_clasifica_y_llega_a_su_organizacion(cliente, db, crear_usuario, headers_de, organizaciones, encolados):
    r = cliente.post(
        "/reportes",
        data={"tipo": "Fuga de gas", "descripcion": "Olor fuerte a gas en la esquina", "lat": "10.46", "lng": "-73.25"},
        files=[("archivos", ("f.jpg", JPG, "image/jpeg"))],
        headers=headers_de(crear_usuario(C)),
    )
    rid = r.json()["id"]
    assert ("clasificar_reporte_ia", (rid,)) in encolados

    resultado = job_reporte.clasificar_reporte_ia.run(rid)
    assert resultado["status"] == "ok"
    reporte = db.get(Reporte, UUID(rid))
    assert reporte.prioridad_ia == PrioridadSolicitud.ALTA
    assert reporte.organizacion_objetivo_id == organizaciones["bomberos"].id

    # El administrador de Bomberos lo ve con la sugerencia de la IA
    admin = crear_usuario(A, organizacion=organizaciones["bomberos"])
    item = cliente.get("/reportes", headers=headers_de(admin)).json()["items"][0]
    assert item["id"] == rid and item["prioridad_ia"] == "alta" and item["razonamiento_ia"]
    assert job_reporte.clasificar_reporte_ia.run(rid)["status"] == "ya_clasificado"


def test_caso_inexistente(db):
    falso = "00000000-0000-0000-0000-000000000000"
    assert job_solicitud.clasificar_prioridad_ia.run(falso)["status"] == "no_encontrada"
    assert job_reporte.clasificar_reporte_ia.run(falso)["status"] == "no_encontrado"


def test_un_redis_caido_no_rompe_la_creacion(monkeypatch):
    from app.jobs import encolar as cola

    monkeypatch.undo()  # quita el reemplazo de la fixture: se usa el encolar real

    class TareaRota:
        name = "tarea"

        def delay(self, *args):
            raise ConnectionError("Redis caído")

    cola.encolar(TareaRota(), "x")  # no lanza
