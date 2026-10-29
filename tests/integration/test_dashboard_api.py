"""Dashboard por rol (A7, backend): alcance de cada rol, conteos y actividad reciente."""

import pytest

from app.models.alerta import Alerta
from app.models.asignacion import Asignacion
from app.models.centro_ayuda import CentroAyuda
from app.models.enums import (
    EstadoAsignacion,
    EstadoCasoPersona,
    EstadoReporte,
    EstadoSolicitud,
    RolUsuario,
    TipoSolicitud,
)
from app.models.persona_desaparecida import PersonaDesaparecida
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.utils.geo import circulo_a_poligono, punto_desde_latlng

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
PUNTO = (10.4631, -73.2532)


@pytest.fixture
def escenario(db, crear_usuario, crear_organizacion):
    """Dos organizaciones con casos propios y uno sin organización."""
    org_a, org_b = crear_organizacion("Bomberos"), crear_organizacion("Cruz Roja")
    ciudadano = crear_usuario(C)
    voluntario_a = crear_usuario(V, organizacion=org_a)
    crear_usuario(V, organizacion=org_b)

    def solicitud(org, estado=EstadoSolicitud.PENDIENTE, descripcion="Necesito agua potable"):
        s = SolicitudAyuda(
            usuario_id=ciudadano.id, descripcion=descripcion, tipo=TipoSolicitud.ALIMENTARIA,
            ubicacion=punto_desde_latlng(*PUNTO), organizacion_manual_id=org.id if org else None, estado=estado,
        )
        db.add(s)
        return s

    def reporte(org, estado=EstadoReporte.PENDIENTE):
        r = Reporte(
            usuario_id=ciudadano.id, tipo="incendio", descripcion="Humo en una bodega",
            ubicacion=punto_desde_latlng(*PUNTO), organizacion_manual_id=org.id if org else None, estado=estado,
        )
        db.add(r)
        return r

    tomada = solicitud(org_a, EstadoSolicitud.EN_PROCESO)
    solicitud(org_a)
    solicitud(org_a, EstadoSolicitud.ATENDIDA)
    solicitud(org_b)
    solicitud(None)
    reporte(org_a)
    reporte(org_a, EstadoReporte.VERIFICADO)
    reporte(org_b)
    reporte(None)
    db.flush()
    db.add(Asignacion(voluntario_id=voluntario_a.id, solicitud_id=tomada.id, estado_asignacion=EstadoAsignacion.ACTIVA))
    db.add(CentroAyuda(nombre="Albergue", tipo="albergue", ubicacion=punto_desde_latlng(*PUNTO),
                       gestionado_por=voluntario_a.id, organizacion_id=org_a.id))
    db.add(Alerta(tipo="inundacion", mensaje="Creciente del río", zona_afectada=circulo_a_poligono(*PUNTO, 500),
                  creado_por=voluntario_a.id, organizacion_id=org_a.id))
    db.add(PersonaDesaparecida(reportado_por=ciudadano.id, nombre="Ana", descripcion="Cabello corto"))
    db.add(PersonaDesaparecida(reportado_por=ciudadano.id, nombre="Luis", descripcion="Alto",
                               estado_caso=EstadoCasoPersona.ENCONTRADO))
    db.flush()
    return {"org_a": org_a, "org_b": org_b, "voluntario_a": voluntario_a}


def test_admin_ve_solo_su_organizacion(cliente, crear_usuario, headers_de, escenario):
    admin = crear_usuario(A, organizacion=escenario["org_a"])
    r = cliente.get("/dashboard", headers=headers_de(admin))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["alcance"] == "organizacion" and d["por_organizacion"] is None
    assert d["resumen"] == {
        "reportes_pendientes": 1,
        "solicitudes_activas": 2,
        "alertas_activas": 1,
        "centros_registrados": 1,
        "personas_buscando": 1,
        "voluntarios_activos": 1,
        "mis_tareas_activas": None,
        "casos_sin_organizacion": None,
    }
    # Su organización: 3 solicitudes + 2 reportes
    assert len(d["recientes"]) == 5
    assert {a["tipo"] for a in d["recientes"]} == {"reporte", "solicitud"}
    fechas = [a["creado_en"] for a in d["recientes"]]
    assert fechas == sorted(fechas, reverse=True)


def test_voluntario_ve_sus_tareas(cliente, headers_de, escenario):
    d = cliente.get("/dashboard", headers=headers_de(escenario["voluntario_a"])).json()
    assert d["resumen"]["mis_tareas_activas"] == 1
    assert d["resumen"]["solicitudes_activas"] == 2


def test_super_admin_ve_todo_y_por_organizacion(cliente, crear_usuario, headers_de, escenario):
    d = cliente.get("/dashboard", headers=headers_de(crear_usuario(S))).json()
    assert d["alcance"] == "global"
    assert d["resumen"]["solicitudes_activas"] >= 4 and d["resumen"]["reportes_pendientes"] >= 3
    assert d["resumen"]["casos_sin_organizacion"] >= 2
    por_org = {o["nombre"]: o for o in d["por_organizacion"]}
    assert por_org["Bomberos"]["solicitudes_activas"] == 2 and por_org["Bomberos"]["reportes_pendientes"] == 1
    assert por_org["Cruz Roja"] == {**por_org["Cruz Roja"], "solicitudes_activas": 1, "reportes_pendientes": 1,
                                    "voluntarios_activos": 1}
    assert len(d["recientes"]) == 9


def test_ciudadano_no_tiene_dashboard(cliente, crear_usuario, headers_de):
    assert cliente.get("/dashboard", headers=headers_de(crear_usuario(C))).status_code == 403


def test_detalle_largo_se_recorta(cliente, db, crear_usuario, headers_de, crear_organizacion):
    org = crear_organizacion()
    ciudadano = crear_usuario(C)
    db.add(SolicitudAyuda(usuario_id=ciudadano.id, descripcion="x" * 300, tipo=TipoSolicitud.RESCATE,
                          ubicacion=punto_desde_latlng(*PUNTO), organizacion_manual_id=org.id))
    db.flush()
    d = cliente.get("/dashboard", headers=headers_de(crear_usuario(A, organizacion=org))).json()
    assert d["recientes"][0]["titulo"] == "Rescate"
    assert len(d["recientes"][0]["detalle"]) == 80 and d["recientes"][0]["detalle"].endswith("…")
