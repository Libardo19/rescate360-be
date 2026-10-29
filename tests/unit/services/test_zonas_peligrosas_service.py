"""Reglas del módulo zonas peligrosas que no necesitan base de datos."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import EstadoZona, NivelZona, RolUsuario
from app.schemas.zonas_peligrosas_schema import ZonaPeligrosaIn, ZonaPeligrosaPatchIn
from app.services import zonas_peligrosas_service as service

ZONA = {"lat": 10.4631, "lng": -73.2532, "radio_m": 800}
CUERPO = {"nombre": "Ribera del río", "tipo_riesgo": "inundacion", "nivel": "alto", "zona": ZONA}


def _usuario(rol: RolUsuario, organizacion_id=None):
    return SimpleNamespace(id=uuid4(), rol=rol, organizacion_id=organizacion_id)


# --- quién ve qué ----------------------------------------------------------------------------


def test_el_administrador_se_limita_a_su_organizacion_por_defecto():
    org = uuid4()
    assert service.organizacion_visible(_usuario(RolUsuario.ADMINISTRADOR, org), "organizacion") == org


def test_el_administrador_puede_pedir_todas():
    assert service.organizacion_visible(_usuario(RolUsuario.ADMINISTRADOR, uuid4()), "todas") is None


@pytest.mark.parametrize("rol", [RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.SUPER_ADMIN])
def test_los_demas_roles_ven_todas(rol):
    org = uuid4() if rol == RolUsuario.VOLUNTARIO else None
    assert service.organizacion_visible(_usuario(rol, org), "organizacion") is None


# --- estados ---------------------------------------------------------------------------------


@pytest.mark.parametrize("rol", list(RolUsuario))
def test_por_defecto_salen_las_vigentes(rol):
    assert service.estados_visibles(_usuario(rol), None) == (EstadoZona.ACTIVA, EstadoZona.EN_MONITOREO)


@pytest.mark.parametrize("rol", [RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN])
def test_administrador_y_super_admin_pueden_pedir_inactivas(rol):
    assert service.estados_visibles(_usuario(rol), EstadoZona.INACTIVA) == (EstadoZona.INACTIVA,)


@pytest.mark.parametrize("rol", [RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO])
def test_ciudadano_y_voluntario_no_ven_inactivas(rol):
    assert service.estados_visibles(_usuario(rol), EstadoZona.INACTIVA) == ()


def test_pedir_en_monitoreo_es_valido_para_todos():
    assert service.estados_visibles(_usuario(RolUsuario.CIUDADANO), EstadoZona.EN_MONITOREO) == (
        EstadoZona.EN_MONITOREO,
    )


# --- zona propia -----------------------------------------------------------------------------


def test_es_propia():
    org = uuid4()
    zona = SimpleNamespace(organizacion_id=org)
    assert service.es_propia(_usuario(RolUsuario.SUPER_ADMIN), zona) is True
    assert service.es_propia(_usuario(RolUsuario.ADMINISTRADOR, org), zona) is True
    assert service.es_propia(_usuario(RolUsuario.VOLUNTARIO, org), zona) is True
    assert service.es_propia(_usuario(RolUsuario.ADMINISTRADOR, uuid4()), zona) is False
    assert service.es_propia(_usuario(RolUsuario.CIUDADANO), zona) is False


def test_una_zona_global_no_es_propia_de_un_administrador():
    assert service.es_propia(_usuario(RolUsuario.ADMINISTRADOR, uuid4()), SimpleNamespace(organizacion_id=None)) is False


# --- validación de la entrada ----------------------------------------------------------------


def test_zona_valida_con_valores_por_defecto():
    datos = ZonaPeligrosaIn(**CUERPO)
    assert datos.estado == EstadoZona.ACTIVA
    assert datos.descripcion is None


def test_el_tipo_de_riesgo_es_texto_libre():
    datos = ZonaPeligrosaIn(**{**CUERPO, "tipo_riesgo": "Desbordamiento del río Guatapurí"})
    assert datos.tipo_riesgo == "Desbordamiento del río Guatapurí"


@pytest.mark.parametrize(
    "cambio",
    [
        {"zona": {**ZONA, "radio_m": 0}},
        {"zona": {**ZONA, "radio_m": 100_001}},
        {"zona": {**ZONA, "lat": 91}},
        {"nivel": "extremo"},
        {"estado": "resuelta"},  # el estado viejo ya no existe
        {"nombre": " "},
        {"tipo_riesgo": "x" * 61},
    ],
)
def test_datos_invalidos_se_rechazan(cambio):
    with pytest.raises(ValidationError):
        ZonaPeligrosaIn(**{**CUERPO, **cambio})


def test_patch_vacio_se_rechaza():
    with pytest.raises(ValidationError):
        ZonaPeligrosaPatchIn()


@pytest.mark.parametrize("campo", ["nombre", "tipo_riesgo", "nivel", "estado", "zona"])
def test_patch_no_acepta_nulo_en_campos_obligatorios(campo):
    with pytest.raises(ValidationError):
        ZonaPeligrosaPatchIn(**{campo: None})


def test_patch_puede_borrar_la_descripcion():
    datos = ZonaPeligrosaPatchIn(descripcion=None)
    assert datos.model_dump(exclude_unset=True) == {"descripcion": None}


def test_patch_solo_incluye_lo_enviado():
    datos = ZonaPeligrosaPatchIn(nivel="bajo")
    assert datos.model_dump(exclude_unset=True) == {"nivel": NivelZona.BAJO}
