from sqlalchemy import select

from app.models.consentimiento import Consentimiento
from app.models.enums import EstadoUsuario, RolUsuario, TipoConsentimiento
from app.models.usuario import Usuario
from tests.conftest import PASSWORD_PRUEBAS

REGISTRO = {
    "nombre": "  Oscar   Ávila ",
    "email": "Oscar@Ejemplo.com",
    "telefono": "+57 300 123 4567",
    "password": "clave-segura-1",
    "acepta_tratamiento_datos": True,
}


def test_registro_crea_ciudadano_y_consentimiento(cliente, db):
    r = cliente.post("/auth/registro", json=REGISTRO)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["access_token"] and cuerpo["refresh_token"]
    assert cuerpo["usuario"]["rol"] == "ciudadano"
    assert cuerpo["usuario"]["nombre"] == "Oscar Ávila"
    assert cuerpo["usuario"]["email"] == "oscar@ejemplo.com"
    assert cuerpo["usuario"]["telefono"] == "+573001234567"
    assert "password_hash" not in cuerpo["usuario"]

    consentimiento = db.scalar(select(Consentimiento).where(Consentimiento.usuario_id == cuerpo["usuario"]["id"]))
    assert consentimiento.tipo == TipoConsentimiento.TRATAMIENTO_DATOS
    assert consentimiento.aceptado is True


def test_registro_no_permite_elegir_rol(cliente, db):
    r = cliente.post("/auth/registro", json={**REGISTRO, "rol": "super_admin"})
    assert r.status_code == 201
    usuario = db.get(Usuario, r.json()["usuario"]["id"])
    assert usuario.rol == RolUsuario.CIUDADANO


def test_registro_sin_aceptar_datos(cliente):
    r = cliente.post("/auth/registro", json={**REGISTRO, "acepta_tratamiento_datos": False})
    assert r.status_code == 422
    assert r.json()["codigo"] == "DATOS_INVALIDOS"
    assert r.json()["errores"] == [
        {
            "campo": "acepta_tratamiento_datos",
            "mensaje": "Debes aceptar la política de tratamiento de datos para registrarte",
        }
    ]


def test_registro_validaciones_en_espanol(cliente):
    r = cliente.post("/auth/registro", json={"email": "no-es-correo", "password": "corta"})
    assert r.status_code == 422
    errores = {e["campo"]: e["mensaje"] for e in r.json()["errores"]}
    assert errores["nombre"] == "Campo obligatorio"
    assert errores["email"] == "Correo electrónico inválido"
    assert errores["password"] == "Debe tener al menos 8 caracteres"


def test_registro_email_duplicado(cliente, crear_usuario):
    crear_usuario(email="oscar@ejemplo.com")
    r = cliente.post("/auth/registro", json=REGISTRO)
    assert r.status_code == 409
    assert r.json()["codigo"] == "EMAIL_YA_REGISTRADO"


def test_login_correcto_actualiza_ultimo_acceso(cliente, crear_usuario, db):
    usuario = crear_usuario(RolUsuario.ADMINISTRADOR)
    r = cliente.post("/auth/login", json={"email": usuario.email.upper(), "password": PASSWORD_PRUEBAS})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["rol"] == "administrador"
    assert r.json()["usuario"]["organizacion_id"] == str(usuario.organizacion_id)
    db.refresh(usuario)
    assert usuario.ultimo_acceso is not None


def test_login_incorrecto_mismo_mensaje(cliente, crear_usuario):
    usuario = crear_usuario()
    mala_clave = cliente.post("/auth/login", json={"email": usuario.email, "password": "otra-clave"})
    no_existe = cliente.post("/auth/login", json={"email": "nadie@prueba.co", "password": "otra-clave"})
    for r in (mala_clave, no_existe):
        assert r.status_code == 401
        assert r.json() == {"detalle": "Correo o contraseña incorrectos", "codigo": "CREDENCIALES_INVALIDAS"}


def test_login_usuario_bloqueado(cliente, crear_usuario):
    usuario = crear_usuario(estado=EstadoUsuario.BLOQUEADO)
    r = cliente.post("/auth/login", json={"email": usuario.email, "password": PASSWORD_PRUEBAS})
    assert r.status_code == 403
    assert r.json()["codigo"] == "USUARIO_BLOQUEADO"


def test_refresh_token(cliente, crear_usuario):
    usuario = crear_usuario()
    sesion = cliente.post("/auth/login", json={"email": usuario.email, "password": PASSWORD_PRUEBAS}).json()

    r = cliente.post("/auth/refresh-token", json={"refresh_token": sesion["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["usuario"]["id"] == str(usuario.id)

    # El access token no sirve como refresh
    r = cliente.post("/auth/refresh-token", json={"refresh_token": sesion["access_token"]})
    assert r.status_code == 401
