"""Contactos de emergencia (A6): a quién le llega el SMS cuando la persona activa el SOS."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.usuarios_schema import normalizar_nombre
from app.utils.telefono import Telefono

MAXIMO_CONTACTOS = 5


class ContactoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=2, max_length=50)
    telefono: Telefono
    parentesco: str | None = Field(default=None, max_length=15)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        return normalizar_nombre(valor)

    @field_validator("parentesco")
    @classmethod
    def _parentesco(cls, valor: str | None) -> str | None:
        return valor or None


class ContactoCambiosIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str | None = Field(default=None, min_length=2, max_length=50)
    telefono: Telefono | None = None
    parentesco: str | None = Field(default=None, max_length=15)

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str | None) -> str | None:
        if valor is None:
            raise ValueError("El nombre no se puede borrar")
        return normalizar_nombre(valor)

    @field_validator("telefono", mode="before")
    @classmethod
    def _telefono(cls, valor):
        if valor is None:
            raise ValueError("El teléfono no se puede borrar")
        return valor


class ContactoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    telefono: str
    parentesco: str | None
    creado_en: datetime
