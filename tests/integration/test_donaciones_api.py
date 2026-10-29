"""Campañas y donaciones (B5) y jobs programados (B6)."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from app.jobs.programados import limpiar_datos_retencion as job_retencion
from app.jobs.programados import marcar_reportes_no_verificables as job_reportes
from app.models.enums import EstadoReporte, RolUsuario
from app.models.reporte import Reporte
from app.utils.geo import punto_desde_latlng

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
CAMPANA = {
    "titulo": "Mercados para La Nevada",
    "descripcion": "Familias afectadas por la creciente",
    "categoria": "alimentos",
    "meta": 200,
    "unidad": "mercados",
    "fecha_fin": (date.today() + timedelta(days=15)).isoformat(),
}


class _SesionDePrueba:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, nombre):
        return getattr(self._db, nombre)

    def close(self):
        pass


# --- campañas ---


def test_admin_crea_y_todos_ven_las_vigentes_con_lo_recaudado(cliente, crear_usuario, headers_de):
    admin = headers_de(crear_usuario(A))
    r = cliente.post("/campanas", json=CAMPANA, headers=admin)
    assert r.status_code == 201, r.text
    campana = r.json()
    assert campana["recaudado"] == 0 and campana["propia"] is True

    for cantidad in (30, 20):
        cliente.post(
            "/donaciones",
            json={"categoria": "alimentos", "cantidad": cantidad, "unidad": "mercados", "campana_id": campana["id"]},
            headers=admin,
        )
    vistas = cliente.get("/campanas", headers=headers_de(crear_usuario(C))).json()
    vista = next(c for c in vistas if c["id"] == campana["id"])
    assert vista["recaudado"] == 50 and vista["propia"] is False


def test_cerrada_solo_la_ve_su_admin_con_todas(cliente, crear_usuario, headers_de):
    usuario_admin = crear_usuario(A)
    admin = headers_de(usuario_admin)
    campana = cliente.post("/campanas", json=CAMPANA, headers=admin).json()
    r = cliente.patch(f"/campanas/{campana['id']}", json={"activa": False}, headers=admin)
    assert r.status_code == 200 and r.json()["activa"] is False

    ciudadano = headers_de(crear_usuario(C))
    assert campana["id"] not in [c["id"] for c in cliente.get("/campanas", headers=ciudadano).json()]
    assert campana["id"] in [c["id"] for c in cliente.get("/campanas", params={"todas": True}, headers=admin).json()]
    otro_admin = headers_de(crear_usuario(A))
    assert cliente.patch(f"/campanas/{campana['id']}", json={"activa": True}, headers=otro_admin).status_code == 403


@pytest.mark.parametrize(
    "cambios", [{"meta": 0}, {"categoria": "joyas"}, {"fecha_fin": (date.today() - timedelta(days=1)).isoformat()}]
)
def test_validaciones_de_campana(cliente, crear_usuario, headers_de, cambios):
    assert cliente.post("/campanas", json={**CAMPANA, **cambios}, headers=headers_de(crear_usuario(A))).status_code == 422


@pytest.mark.parametrize("rol", [C, V])
def test_ciudadano_y_voluntario_no_gestionan(cliente, crear_usuario, headers_de, rol):
    h = headers_de(crear_usuario(rol))
    assert cliente.post("/campanas", json=CAMPANA, headers=h).status_code == 403
    assert cliente.get("/donaciones", headers=h).status_code == 403


# --- donaciones ---


def test_dinero_necesita_monto_y_suma_el_monto(cliente, crear_usuario, headers_de):
    admin = headers_de(crear_usuario(A))
    campana = cliente.post("/campanas", json={**CAMPANA, "categoria": "dinero", "unidad": "COP", "meta": 1_000_000}, headers=admin).json()
    base = {"categoria": "dinero", "cantidad": 1, "unidad": "transferencia", "campana_id": campana["id"]}
    assert cliente.post("/donaciones", json=base, headers=admin).status_code == 422
    assert cliente.post("/donaciones", json={**base, "monto": 250_000}, headers=admin).status_code == 201
    vista = next(c for c in cliente.get("/campanas", headers=admin).json() if c["id"] == campana["id"])
    assert vista["recaudado"] == 250_000


def test_la_categoria_debe_coincidir_con_la_campana(cliente, crear_usuario, headers_de):
    admin = headers_de(crear_usuario(A))
    campana = cliente.post("/campanas", json=CAMPANA, headers=admin).json()
    r = cliente.post(
        "/donaciones", json={"categoria": "ropa", "cantidad": 3, "unidad": "bolsas", "campana_id": campana["id"]}, headers=admin
    )
    assert r.status_code == 422 and r.json()["codigo"] == "CATEGORIA_DISTINTA"


def test_cada_organizacion_ve_las_suyas_y_cambia_el_estado(cliente, crear_usuario, headers_de):
    admin_a, admin_b = headers_de(crear_usuario(A)), headers_de(crear_usuario(A))
    donacion = cliente.post("/donaciones", json={"categoria": "agua", "cantidad": 40, "unidad": "botellones"}, headers=admin_a).json()
    assert donacion["estado"] == "recibida"
    assert cliente.get("/donaciones", headers=admin_b).json()["total"] == 0
    assert cliente.get("/donaciones", headers=admin_a).json()["total"] == 1
    assert cliente.get("/donaciones", headers=headers_de(crear_usuario(S))).json()["total"] >= 1

    url = f"/donaciones/{donacion['id']}/estado"
    assert cliente.patch(url, json={"estado": "entregada"}, headers=admin_b).status_code == 403
    assert cliente.patch(url, json={"estado": "entregada"}, headers=admin_a).json()["estado"] == "entregada"


# --- jobs programados ---


def test_reportes_pendientes_de_mas_de_72_horas_quedan_no_verificables(db, crear_usuario, monkeypatch):
    monkeypatch.setattr(job_reportes, "SessionLocal", lambda: _SesionDePrueba(db))
    autor = crear_usuario(C)
    viejo = Reporte(usuario_id=autor.id, tipo="incendio", descripcion="Humo", ubicacion=punto_desde_latlng(10.4, -73.2))
    nuevo = Reporte(usuario_id=autor.id, tipo="robo", descripcion="Robo", ubicacion=punto_desde_latlng(10.4, -73.2))
    db.add_all([viejo, nuevo])
    db.flush()
    viejo.creado_en = datetime.now(UTC) - timedelta(hours=73)
    db.flush()
    assert job_reportes.marcar_reportes_no_verificables.run()["marcados"] >= 1
    db.refresh(viejo)
    db.refresh(nuevo)
    assert viejo.estado == EstadoReporte.NO_VERIFICABLE and nuevo.estado == EstadoReporte.PENDIENTE


def test_retencion_borra_ubicaciones_viejas(db, crear_usuario, monkeypatch):
    monkeypatch.setattr(job_retencion, "SessionLocal", lambda: _SesionDePrueba(db))
    vieja, reciente = crear_usuario(C), crear_usuario(C)
    for usuario, dias in ((vieja, 31), (reciente, 1)):
        usuario.ubicacion_actual = punto_desde_latlng(10.4, -73.2)
        usuario.ubicacion_actualizada_en = datetime.now(UTC) - timedelta(days=dias)
    db.flush()
    assert job_retencion.limpiar_datos_retencion.run()["ubicaciones"] >= 1
    db.refresh(vieja)
    db.refresh(reciente)
    assert vieja.ubicacion_actual is None and reciente.ubicacion_actual is not None
