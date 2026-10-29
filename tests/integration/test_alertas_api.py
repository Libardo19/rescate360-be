"""Alertas por zona (B3): publicar, alcance por rol, "las que me afectan", vencimiento, push y mapa."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.jobs.eventos import notificar_alerta_zona as job_alerta
from app.jobs.eventos import notificar_persona_encontrada as job_persona
from app.jobs.eventos import notificar_voluntarios_cercanos as job_voluntarios
from app.jobs.programados import expirar_alertas as job_expirar
from app.models.alerta import Alerta
from app.models.dispositivo import Dispositivo
from app.models.enums import EstadoAlerta, PlataformaDispositivo, RolUsuario
from app.models.reporte import Reporte
from app.services import notificaciones_service
from app.utils.geo import punto_desde_latlng

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
VALLEDUPAR = (10.4631, -73.2532)
ALERTA = {
    "titulo": "Creciente del río Guatapurí",
    "tipo": "inundacion",
    "mensaje": "Aléjate de la ribera y sube a un lugar alto.",
    "nivel": "alto",
    "zona": {"lat": VALLEDUPAR[0], "lng": VALLEDUPAR[1], "radio_m": 2000},
}


class _SesionDePrueba:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, nombre):
        return getattr(self._db, nombre)

    def close(self):
        pass


@pytest.fixture
def push(db, monkeypatch):
    """Los jobs usan la sesión de la prueba y el push queda en una lista (nunca va a Firebase)."""
    enviados: list[tuple[list[str], str]] = []
    for job in (job_alerta, job_persona, job_voluntarios, job_expirar):
        monkeypatch.setattr(job, "SessionLocal", lambda: _SesionDePrueba(db))
    monkeypatch.setattr(
        notificaciones_service.firebase_client,
        "enviar_push",
        lambda tokens, titulo, cuerpo, datos=None: enviados.append((sorted(tokens), titulo)) or [],
    )
    return enviados


def _ubicar(db, usuario, lat, lng, hace_horas=0):
    usuario.ubicacion_actual = punto_desde_latlng(lat, lng)
    usuario.ubicacion_actualizada_en = datetime.now(UTC) - timedelta(hours=hace_horas)
    db.add(Dispositivo(usuario_id=usuario.id, token_push=f"tok-{usuario.id}", plataforma=PlataformaDispositivo.ANDROID))
    db.flush()


def _publicar(cliente, headers, **cambios):
    return cliente.post("/alertas", json={**ALERTA, **cambios}, headers=headers)


# --- publicar ---


def test_admin_publica_en_su_organizacion_y_se_encola_el_push(cliente, crear_usuario, headers_de, encolados):
    admin = crear_usuario(A)
    r = _publicar(cliente, headers_de(admin))
    assert r.status_code == 201, r.text
    alerta = r.json()
    assert alerta["estado"] == "activa" and alerta["origen"] == "manual" and alerta["nivel"] == "alto"
    assert alerta["organizacion_id"] == str(admin.organizacion_id) and alerta["propia"] is True
    assert alerta["zona"] == {"lat": pytest.approx(VALLEDUPAR[0]), "lng": pytest.approx(VALLEDUPAR[1]), "radio_m": 2000}
    vence = datetime.fromisoformat(alerta["expira_en"])
    assert timedelta(hours=23) < vence - datetime.now(UTC) <= timedelta(hours=24)
    assert ("notificar_alerta_zona", (alerta["id"],)) in encolados


@pytest.mark.parametrize("rol", [C, V])
def test_ciudadano_y_voluntario_no_publican(cliente, crear_usuario, headers_de, rol):
    assert _publicar(cliente, headers_de(crear_usuario(rol))).status_code == 403


def test_admin_no_publica_en_otra_organizacion(cliente, crear_usuario, crear_organizacion, headers_de):
    r = _publicar(cliente, headers_de(crear_usuario(A)), organizacion_id=str(crear_organizacion().id))
    assert r.status_code == 403 and r.json()["codigo"] == "ALERTA_ORGANIZACION_NO_PERMITIDA"


def test_super_admin_publica_global(cliente, crear_usuario, headers_de):
    assert _publicar(cliente, headers_de(crear_usuario(S))).json()["organizacion_id"] is None


@pytest.mark.parametrize(
    "cambios", [{"zona": {"lat": 10, "lng": -73, "radio_m": 0}}, {"horas_vigencia": 500}, {"titulo": "x"}]
)
def test_validaciones(cliente, crear_usuario, headers_de, cambios):
    assert _publicar(cliente, headers_de(crear_usuario(A)), **cambios).status_code == 422


# --- listar ---


def test_las_activas_son_publicas_y_se_filtran_por_mi_punto(cliente, crear_usuario, headers_de):
    admin = headers_de(crear_usuario(A))
    cerca = _publicar(cliente, admin).json()
    lejos = _publicar(cliente, admin, zona={"lat": 4.711, "lng": -74.072, "radio_m": 1000}).json()
    ciudadano = headers_de(crear_usuario(C))

    ids = [a["id"] for a in cliente.get("/alertas", headers=ciudadano).json()["items"]]
    assert {cerca["id"], lejos["id"]} <= set(ids)
    mias = cliente.get("/alertas", params={"lat": 10.47, "lng": -73.25}, headers=ciudadano).json()["items"]
    assert [a["id"] for a in mias] == [cerca["id"]]
    assert cliente.get("/alertas", params={"lat": 10.4}, headers=ciudadano).status_code == 422


def test_canceladas_solo_las_ve_un_administrador(cliente, crear_usuario, headers_de):
    admin = headers_de(crear_usuario(A))
    alerta = _publicar(cliente, admin).json()
    assert cliente.post(f"/alertas/{alerta['id']}/cancelar", headers=admin).json()["estado"] == "cancelada"

    ciudadano = headers_de(crear_usuario(C))
    ids = [a["id"] for a in cliente.get("/alertas", params={"estado": "cancelada"}, headers=ciudadano).json()["items"]]
    assert alerta["id"] not in ids
    assert cliente.get(f"/alertas/{alerta['id']}", headers=ciudadano).status_code == 404
    assert cliente.get(f"/alertas/{alerta['id']}", headers=admin).status_code == 200


# --- editar y cancelar ---


def test_editar_extiende_la_vigencia(cliente, crear_usuario, headers_de):
    admin = headers_de(crear_usuario(A))
    alerta = _publicar(cliente, admin, horas_vigencia=1).json()
    r = cliente.patch(f"/alertas/{alerta['id']}", json={"horas_vigencia": 48, "nivel": "medio"}, headers=admin)
    assert r.status_code == 200 and r.json()["nivel"] == "medio"
    assert datetime.fromisoformat(r.json()["expira_en"]) - datetime.now(UTC) > timedelta(hours=47)
    assert cliente.patch(f"/alertas/{alerta['id']}", json={}, headers=admin).status_code == 422


def test_otro_admin_no_la_toca_y_cancelada_no_se_edita(cliente, crear_usuario, headers_de):
    admin = headers_de(crear_usuario(A))
    alerta = _publicar(cliente, admin).json()
    otro = headers_de(crear_usuario(A))
    assert cliente.post(f"/alertas/{alerta['id']}/cancelar", headers=otro).status_code == 403
    cliente.post(f"/alertas/{alerta['id']}/cancelar", headers=admin)
    r = cliente.patch(f"/alertas/{alerta['id']}", json={"nivel": "bajo"}, headers=admin)
    assert r.status_code == 409 and r.json()["codigo"] == "ALERTA_NO_ACTIVA"


# --- jobs ---


def test_push_solo_a_quien_esta_dentro_con_ubicacion_reciente(cliente, db, crear_usuario, headers_de, push):
    dentro, fuera, vieja = crear_usuario(C), crear_usuario(C), crear_usuario(C)
    _ubicar(db, dentro, 10.465, -73.253)
    _ubicar(db, fuera, 10.60, -73.25)
    _ubicar(db, vieja, 10.465, -73.253, hace_horas=48)
    alerta = _publicar(cliente, headers_de(crear_usuario(A))).json()

    resultado = job_alerta.notificar_alerta_zona.run(alerta["id"])
    assert resultado["usuarios"] == 1
    assert push == [([f"tok-{dentro.id}"], "Alerta alto: Creciente del río Guatapurí")]


def test_expiran_las_vencidas(cliente, db, crear_usuario, headers_de, push):
    admin = headers_de(crear_usuario(A))
    alerta = _publicar(cliente, admin).json()
    fila = db.get(Alerta, UUID(alerta["id"]))
    fila.expira_en = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    assert job_expirar.expirar_alertas.run()["expiradas"] >= 1
    db.refresh(fila)
    assert fila.estado == EstadoAlerta.EXPIRADA
    # Una expirada ya no avisa a nadie
    assert job_alerta.notificar_alerta_zona.run(alerta["id"])["status"] == "no_aplica"


def test_voluntarios_cercanos_de_la_organizacion(cliente, db, crear_usuario, crear_organizacion, headers_de, push):
    org = crear_organizacion()
    cerca, lejos, otra_org = crear_usuario(V, organizacion=org), crear_usuario(V, organizacion=org), crear_usuario(V)
    _ubicar(db, cerca, 10.47, -73.25)
    _ubicar(db, lejos, 11.0, -73.25)
    _ubicar(db, otra_org, 10.47, -73.25)
    reporte = Reporte(
        usuario_id=crear_usuario(C).id, tipo="incendio", descripcion="Humo en una bodega",
        ubicacion=punto_desde_latlng(*VALLEDUPAR), organizacion_manual_id=org.id,
    )
    db.add(reporte)
    db.flush()
    assert job_voluntarios.notificar_voluntarios_cercanos.run(str(reporte.id))["voluntarios"] == 1
    assert push[0][0] == [f"tok-{cerca.id}"]

    reporte.organizacion_manual_id = None
    db.flush()
    assert job_voluntarios.notificar_voluntarios_cercanos.run(str(reporte.id))["status"] == "sin_organizacion"


def test_enrutar_un_reporte_avisa_a_sus_voluntarios(cliente, crear_usuario, crear_organizacion, headers_de, encolados, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    reporte = cliente.post(
        "/reportes",
        data={"tipo": "incendio", "descripcion": "Humo", "lat": "10.46", "lng": "-73.25"},
        headers=headers_de(crear_usuario(C)),
    ).json()
    r = cliente.patch(
        f"/reportes/{reporte['id']}/organizacion",
        json={"organizacion_id": str(crear_organizacion().id)},
        headers=headers_de(crear_usuario(S)),
    )
    assert r.status_code == 200, r.text
    assert ("notificar_voluntarios_cercanos", (reporte["id"],)) in encolados


def test_persona_encontrada_avisa_a_quien_la_reporto(cliente, db, crear_usuario, headers_de, encolados, push, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    autor = crear_usuario(C)
    _ubicar(db, autor, *VALLEDUPAR)
    h = headers_de(autor)
    persona = cliente.post(
        "/personas-desaparecidas",
        data={
            "nombre": "Ana Ruiz", "edad": "30", "sexo": "femenino", "fecha_vista": "2026-10-20",
            "lugar": "Centro", "descripcion": "Cabello corto", "contacto_nombre": "Luis",
            "contacto_telefono": "3001234567",
        },
        headers=h,
    ).json()
    cliente.patch(f"/personas-desaparecidas/{persona['id']}/estado", json={"estado": "encontrado"}, headers=h)
    assert ("notificar_persona_encontrada", (persona["id"],)) in encolados
    job_persona.notificar_persona_encontrada.run(persona["id"])
    assert push == [([f"tok-{autor.id}"], "Persona encontrada")]


# --- mapa y dashboard ---


def test_capa_de_alertas_en_el_mapa(cliente, crear_usuario, headers_de):
    alerta = _publicar(cliente, headers_de(crear_usuario(A))).json()
    puntos = cliente.get("/mapa", params={"capas": "alertas"}, headers=headers_de(crear_usuario(C))).json()["puntos"]
    punto = next(p for p in puntos if p["id"] == alerta["id"])
    assert punto["capa"] == "alerta" and punto["radio_m"] == 2000 and punto["prioridad"] == "alto"
    assert punto["activo"] is True and punto["aproximada"] is False and punto["propio"] is False
