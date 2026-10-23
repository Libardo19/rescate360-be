"""Reglas de acceso del service, sin base de datos (SimpleNamespace en lugar del ORM)."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.excepciones import SinPermiso
from app.models.enums import RolUsuario
from app.services import solicitudes_ayuda_service as service


def _usuario(rol: RolUsuario, organizacion_id=None):
    return SimpleNamespace(id=uuid4(), rol=rol, organizacion_id=organizacion_id)


def _solicitud(usuario_id=None, objetivo=None, manual=None):
    return SimpleNamespace(
        usuario_id=usuario_id or uuid4(),
        organizacion_objetivo_id=objetivo,
        organizacion_manual_id=manual,
    )


def test_organizacion_efectiva_prefiere_la_manual():
    manual, objetivo = uuid4(), uuid4()
    assert service.organizacion_efectiva(_solicitud(objetivo=objetivo, manual=manual)) == manual


def test_organizacion_efectiva_usa_la_objetivo_si_no_hay_manual():
    objetivo = uuid4()
    assert service.organizacion_efectiva(_solicitud(objetivo=objetivo)) == objetivo


def test_organizacion_efectiva_sin_enrutar_es_none():
    assert service.organizacion_efectiva(_solicitud()) is None


def test_ciudadano_accede_a_su_solicitud():
    ciudadano = _usuario(RolUsuario.CIUDADANO)
    service.verificar_acceso(ciudadano, _solicitud(usuario_id=ciudadano.id))


def test_ciudadano_no_accede_a_la_de_otro():
    with pytest.raises(SinPermiso) as error:
        service.verificar_acceso(_usuario(RolUsuario.CIUDADANO), _solicitud())
    assert error.value.codigo == "SOLICITUD_FUERA_DE_ALCANCE"


@pytest.mark.parametrize("rol", [RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR])
def test_operativo_accede_a_solicitud_de_su_organizacion(rol):
    org = uuid4()
    service.verificar_acceso(_usuario(rol, org), _solicitud(objetivo=org))


@pytest.mark.parametrize("rol", [RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR])
def test_operativo_no_accede_a_solicitud_de_otra_organizacion(rol):
    with pytest.raises(SinPermiso):
        service.verificar_acceso(_usuario(rol, uuid4()), _solicitud(objetivo=uuid4()))


def test_la_organizacion_manual_le_quita_el_caso_a_la_sugerida():
    mi_org = uuid4()
    admin = _usuario(RolUsuario.ADMINISTRADOR, mi_org)
    with pytest.raises(SinPermiso):
        service.verificar_acceso(admin, _solicitud(objetivo=mi_org, manual=uuid4()))


@pytest.mark.parametrize("rol", [RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR])
def test_solicitud_sin_enrutar_no_la_ve_un_operativo(rol):
    with pytest.raises(SinPermiso):
        service.verificar_acceso(_usuario(rol, uuid4()), _solicitud())


def test_super_admin_ve_la_solicitud_sin_enrutar():
    service.verificar_acceso(_usuario(RolUsuario.SUPER_ADMIN), _solicitud())
