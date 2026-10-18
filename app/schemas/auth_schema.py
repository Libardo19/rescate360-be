from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import BCRYPT_MAX_BYTES
from app.schemas.usuarios_schema import UsuarioOut
from app.utils.telefono import Telefono


class RegistroIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=50)
    email: EmailStr = Field(max_length=100)
    telefono: Telefono | None = None
    password: str = Field(min_length=8)
    # Autorización de tratamiento de datos (Ley 1581): checkbox sin premarcar en la app.
    acepta_tratamiento_datos: bool

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        valor = " ".join(valor.split())
        if len(valor) < 2:
            raise ValueError("Debe tener al menos 2 caracteres")
        return valor

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        return valor.lower()

    @field_validator("password")
    @classmethod
    def _password(cls, valor: str) -> str:
        if len(valor.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"La contraseña no puede superar {BCRYPT_MAX_BYTES} bytes")
        return valor

    @field_validator("acepta_tratamiento_datos")
    @classmethod
    def _acepta(cls, valor: bool) -> bool:
        if not valor:
            raise ValueError("Debes aceptar la política de tratamiento de datos para registrarte")
        return valor


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        return valor.lower()


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1)


class SesionOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut
