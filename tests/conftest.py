"""Fixtures comunes de las pruebas.

- Base de datos propia de pruebas: `<DATABASE_URL>_test` (o TEST_DATABASE_URL).
  Se crea si no existe y se migra con Alembic una vez por sesión.
- Cada prueba corre dentro de una transacción que se deshace al final: las pruebas
  no se ensucian entre sí, aunque el service haga `db.commit()`.
- Fixtures para crear organizaciones y usuarios de cualquier rol, y headers con token:

    def test_algo(cliente, crear_usuario, headers_de):
        admin = crear_usuario(RolUsuario.ADMINISTRADOR)          # crea su organización
        r = cliente.get("/reportes", headers=headers_de(admin))
"""

import itertools
import os
from collections.abc import Callable, Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import crear_access_token, hash_password
from app.main import app
from app.models.enums import EstadoUsuario, RolUsuario, TipoOrganizacion
from app.models.organizacion import Organizacion
from app.models.usuario import Usuario

PASSWORD_PRUEBAS = "clave-de-prueba-123"
_contador = itertools.count(1)


def _url_pruebas() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    url = make_url(get_settings().database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


def _crear_bd_si_no_existe(url: str) -> None:
    url_obj = make_url(url)
    admin = create_engine(url_obj.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        existe = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url_obj.database})
        if not existe:
            conn.execute(text(f'CREATE DATABASE "{url_obj.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine_pruebas():
    url = _url_pruebas()
    _crear_bd_si_no_existe(url)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def encolados(monkeypatch) -> list[tuple[str, tuple]]:
    """Las pruebas no mandan jobs al worker real: se registran (nombre de la tarea, argumentos)."""
    from app.jobs import encolar as cola

    registro: list[tuple[str, tuple]] = []
    monkeypatch.setattr(cola, "encolar", lambda tarea, *args: registro.append((tarea.name.rsplit(".", 1)[-1], args)))
    return registro


@pytest.fixture
def db(engine_pruebas) -> Iterator[Session]:
    conexion = engine_pruebas.connect()
    transaccion = conexion.begin()
    # Los commit() del código se vuelven SAVEPOINT dentro de la transacción de la prueba.
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


@pytest.fixture
def cliente(db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def crear_organizacion(db) -> Callable[..., Organizacion]:
    def _crear(nombre: str | None = None, tipo: TipoOrganizacion = TipoOrganizacion.ONG) -> Organizacion:
        org = Organizacion(nombre=nombre or f"Organización {next(_contador)}", tipo=tipo)
        db.add(org)
        db.flush()
        return org

    return _crear


@pytest.fixture
def crear_usuario(db, crear_organizacion) -> Callable[..., Usuario]:
    """Crea un usuario del rol pedido. Voluntario y administrador reciben una organización nueva si no se pasa una."""

    def _crear(
        rol: RolUsuario = RolUsuario.CIUDADANO,
        organizacion: Organizacion | None = None,
        estado: EstadoUsuario = EstadoUsuario.ACTIVO,
        email: str | None = None,
        password: str = PASSWORD_PRUEBAS,
    ) -> Usuario:
        if rol in (RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR) and organizacion is None:
            organizacion = crear_organizacion()
        n = next(_contador)
        usuario = Usuario(
            nombre=f"{rol.value} {n}",
            email=email or f"{rol.value}{n}@prueba.co",
            password_hash=hash_password(password),
            rol=rol,
            estado=estado,
            organizacion_id=organizacion.id if organizacion else None,
        )
        db.add(usuario)
        db.flush()
        return usuario

    return _crear


@pytest.fixture
def headers_de() -> Callable[[Usuario], dict]:
    def _headers(usuario: Usuario) -> dict:
        return {"Authorization": f"Bearer {crear_access_token(usuario)}"}

    return _headers
