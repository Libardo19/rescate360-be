"""Tests unitarios del servicio de centros de ayuda."""

from uuid import uuid4

import pytest

from app.core.excepciones import SinPermiso
from app.models.enums import RolUsuario, TipoOrganizacion
from app.models.organizacion import Organizacion
from app.models.usuario import Usuario
from app.services import centros_ayuda_service
from app.schemas.centros_ayuda_schema import CentroAyudaIn, CentroAyudaUpdate


def _crear_org(db, nombre: str | None = None) -> Organizacion:
    org = Organizacion(nombre=nombre or f"Org {uuid4()}", tipo=TipoOrganizacion.ONG)
    db.add(org)
    db.flush()
    return org


def _crear_usuario(db, rol: RolUsuario, organizacion: Organizacion | None = None):
    u = Usuario(
        nombre=f"{rol.value} {uuid4()}",
        email=f"{uuid4()}@test.co",
        password_hash="hash",
        rol=rol,
        organizacion_id=organizacion.id if organizacion else None,
    )
    db.add(u)
    db.flush()
    return u


def test_admin_solo_puede_modificar_centro_de_su_organizacion(db):
    org1 = _crear_org(db)
    org2 = _crear_org(db)
    admin1 = _crear_usuario(db, RolUsuario.ADMINISTRADOR, org1)
    admin2 = _crear_usuario(db, RolUsuario.ADMINISTRADOR, org2)
    datos = CentroAyudaIn(nombre="Centro 1", tipo="albergue", estado="activo", direccion="Calle 1", lat=10.46, lng=-73.25)
    centro = centros_ayuda_service.crear(db, admin1, datos)
    # admin2 no puede modificar
    with pytest.raises(SinPermiso):
        centros_ayuda_service.actualizar(db, admin2, centro.id, CentroAyudaUpdate(estado="inactivo"))


def test_voluntario_no_puede_modificar_centro(db):
    org = _crear_org(db)
    admin = _crear_usuario(db, RolUsuario.ADMINISTRADOR, org)
    vol = _crear_usuario(db, RolUsuario.VOLUNTARIO, org)
    datos = CentroAyudaIn(nombre="Centro 2", tipo="comedor", estado="activo", direccion="Calle 2", lat=10.47, lng=-73.26)
    centro = centros_ayuda_service.crear(db, admin, datos)
    with pytest.raises(SinPermiso):
        centros_ayuda_service.actualizar(db, vol, centro.id, CentroAyudaUpdate(estado="inactivo"))


def test_super_admin_puede_modificar_cualquier_centro(db):
    org1 = _crear_org(db)
    org2 = _crear_org(db)
    admin1 = _crear_usuario(db, RolUsuario.ADMINISTRADOR, org1)
    superadmin = _crear_usuario(db, RolUsuario.SUPER_ADMIN, None)
    datos = CentroAyudaIn(nombre="Centro 3", tipo="puesto_medico", estado="activo", direccion="Calle 3", lat=10.48, lng=-73.24)
    centro = centros_ayuda_service.crear(db, admin1, datos)
    actualizado = centros_ayuda_service.actualizar(db, superadmin, centro.id, CentroAyudaUpdate(estado="en_operacion"))
    assert actualizado.estado == "en_operacion"
