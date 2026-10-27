from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest

from app.core.config import get_settings
from app.core.excepciones import NoAutenticado
from app.core.security import (
    TOKEN_ACCESS,
    TOKEN_REFRESH,
    crear_access_token,
    crear_refresh_token,
    decodificar_token,
    generar_codigo_activacion,
    hash_codigo,
    hash_password,
    verify_password,
)
from app.models.enums import RolUsuario


def _usuario(rol=RolUsuario.ADMINISTRADOR, organizacion_id=None):
    return SimpleNamespace(id=uuid4(), rol=rol, organizacion_id=organizacion_id or uuid4())


def test_hash_y_verificacion():
    h = hash_password("clave-segura")
    assert h != "clave-segura"
    assert verify_password("clave-segura", h)
    assert not verify_password("otra-clave", h)


def test_contrasena_de_mas_de_72_bytes():
    with pytest.raises(ValueError):
        hash_password("ñ" * 37)  # 74 bytes en UTF-8
    assert not verify_password("a" * 73, hash_password("a" * 72))


def test_hash_corrupto_no_revienta():
    assert not verify_password("clave", "no-es-un-hash")


def test_access_token_lleva_rol_y_organizacion():
    usuario = _usuario()
    payload = decodificar_token(crear_access_token(usuario), TOKEN_ACCESS)
    assert payload["sub"] == str(usuario.id)
    assert payload["rol"] == "administrador"
    assert payload["organizacion_id"] == str(usuario.organizacion_id)


def test_no_se_acepta_refresh_como_access():
    token = crear_refresh_token(_usuario())
    with pytest.raises(NoAutenticado) as error:
        decodificar_token(token, TOKEN_ACCESS)
    assert error.value.codigo == "TOKEN_INVALIDO"
    assert decodificar_token(token, TOKEN_REFRESH)["tipo"] == TOKEN_REFRESH


def test_token_expirado():
    s = get_settings()
    ayer = datetime.now(UTC) - timedelta(days=1)
    token = jwt.encode({"sub": "x", "tipo": TOKEN_ACCESS, "exp": ayer}, s.jwt_secret, algorithm=s.jwt_algorithm)
    with pytest.raises(NoAutenticado) as error:
        decodificar_token(token, TOKEN_ACCESS)
    assert error.value.codigo == "TOKEN_EXPIRADO"


def test_token_con_otra_firma():
    token = jwt.encode({"sub": "x", "tipo": TOKEN_ACCESS, "exp": datetime.now(UTC) + timedelta(minutes=5)}, "otra")
    with pytest.raises(NoAutenticado):
        decodificar_token(token, TOKEN_ACCESS)


def test_codigo_de_activacion_legible_y_sin_caracteres_ambiguos():
    codigos = {generar_codigo_activacion() for _ in range(200)}
    assert len(codigos) == 200  # no se repiten
    for codigo in codigos:
        assert len(codigo) == 9 and codigo[4] == "-"
        assert not set(codigo) & set("01OIL")


def test_hash_de_codigo_ignora_guion_espacios_y_mayusculas():
    assert hash_codigo("K7MZ-Q3RT") == hash_codigo("k7mz q3rt") == hash_codigo("K7MZQ3RT")
    assert hash_codigo("K7MZ-Q3RT") != hash_codigo("K7MZ-Q3RA")
    assert len(hash_codigo("K7MZ-Q3RT")) == 64
