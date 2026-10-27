import pytest

from app.core.security import verify_password
from app.models.enums import EstadoUsuario, RolUsuario
from scripts.seed.crear_super_admin import ErrorSeed, crear_super_admin


def test_crea_el_super_admin_y_es_idempotente(db):
    usuario, creado = crear_super_admin(db, nombre="Raíz", email="Raiz@Rescate360.co", password="clave-super-1")
    assert creado
    assert usuario.rol == RolUsuario.SUPER_ADMIN
    assert usuario.estado == EstadoUsuario.ACTIVO
    assert usuario.organizacion_id is None
    assert usuario.email == "raiz@rescate360.co"
    assert verify_password("clave-super-1", usuario.password_hash)

    otra_vez, creado = crear_super_admin(db, nombre="Raíz", email="raiz@rescate360.co", password="otra-clave-1")
    assert not creado and otra_vez.id == usuario.id
    assert verify_password("clave-super-1", otra_vez.password_hash)  # no le cambia la contraseña


def test_no_convierte_en_super_admin_a_una_cuenta_existente(db, crear_usuario):
    ciudadano = crear_usuario(email="vecino@prueba.co")
    with pytest.raises(ErrorSeed):
        crear_super_admin(db, nombre="X", email=ciudadano.email, password="clave-super-1")


@pytest.mark.parametrize(("email", "password"), [("", "clave-super-1"), ("a@b.co", ""), ("a@b.co", "corta")])
def test_datos_incompletos(db, email, password):
    with pytest.raises(ErrorSeed):
        crear_super_admin(db, nombre="X", email=email, password=password)
