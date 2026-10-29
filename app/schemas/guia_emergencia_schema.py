"""Guía de emergencia (A7). El contenido son pasos separados por salto de línea."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

Categoria = Literal[
    "sismo", "inundacion", "incendio", "accidente", "deslizamiento", "robo", "medica", "desaparecidos", "general"
]


def _limpiar_pasos(pasos: list[str]) -> list[str]:
    limpios = [" ".join(p.split()) for p in pasos if p.strip()]
    if not limpios:
        raise ValueError("La guía necesita al menos un paso")
    return limpios


class GuiaIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str = Field(min_length=3, max_length=50)
    categoria: Categoria
    pasos: list[str] = Field(min_length=1, max_length=20)

    @field_validator("pasos")
    @classmethod
    def _pasos(cls, valor: list[str]) -> list[str]:
        return _limpiar_pasos(valor)


class GuiaCambiosIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str | None = Field(default=None, min_length=3, max_length=50)
    categoria: Categoria | None = None
    pasos: list[str] | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("pasos")
    @classmethod
    def _pasos(cls, valor: list[str] | None) -> list[str] | None:
        return _limpiar_pasos(valor) if valor is not None else None


class GuiaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    titulo: str
    categoria: str
    contenido: str

    @computed_field
    @property
    def pasos(self) -> list[str]:
        return [p for p in self.contenido.split("\n") if p.strip()]
