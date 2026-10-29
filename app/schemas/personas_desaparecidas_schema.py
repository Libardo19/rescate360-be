"""Schemas de personas desaparecidas (A5)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from geoalchemy2.elements import WKBElement, WKTElement
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import EstadoCasoPersona
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.utils.geo import latlng_desde_punto
from app.utils.telefono import Telefono

Sexo = Literal["femenino", "masculino", "otro"]
EDAD_MAYORIA = 18

# Va en el detalle de cada ficha: la app y el panel lo muestran tal cual
AVISO_LEGAL = (
    "Para denunciar una desaparición no hay que esperar 72 horas: llama a la Policía (123) o acude a la "
    "Fiscalía. Si crees que se trata de una desaparición forzada, puedes pedir ante cualquier juez el "
    "Mecanismo de Búsqueda Urgente (Ley 971 de 2005)."
)


def _vacio_a_none(valor: str | None) -> str | None:
    return valor or None


class _Ficha(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("fecha_vista", check_fields=False)
    @classmethod
    def _no_futura(cls, valor: date | None) -> date | None:
        if valor is not None and valor > date.today():
            raise ValueError("La fecha en que se vio por última vez no puede ser futura")
        return valor

    @field_validator("estatura", "senas_particulares", "vestimenta", check_fields=False)
    @classmethod
    def _opcionales(cls, valor: str | None) -> str | None:
        return _vacio_a_none(valor)


class PersonaIn(_Ficha):
    """Campos del formulario multipart de POST /personas-desaparecidas (la foto va aparte)."""

    nombre: str = Field(min_length=3, max_length=50)
    edad: int = Field(ge=0, le=120)
    sexo: Sexo
    estatura: str | None = Field(default=None, max_length=10)
    fecha_vista: date
    lugar: str = Field(min_length=3, max_length=100)
    descripcion: str = Field(min_length=3, max_length=2000)
    senas_particulares: str | None = Field(default=None, max_length=1000)
    vestimenta: str | None = Field(default=None, max_length=1000)
    contacto_nombre: str = Field(min_length=3, max_length=50)
    contacto_telefono: Telefono
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    # Autorización para publicar la foto (consentimiento `foto_persona`); obligatoria si hay foto
    acepta_publicar_foto: bool = False

    @model_validator(mode="after")
    def _coordenadas_completas(self) -> "PersonaIn":
        if (self.lat is None) != (self.lng is None):
            raise ValueError("Envía lat y lng juntos, o ninguno")
        return self


class PersonaEdicionIn(_Ficha):
    """PATCH: solo se cambia lo que llega."""

    nombre: str | None = Field(default=None, min_length=3, max_length=50)
    edad: int | None = Field(default=None, ge=0, le=120)
    sexo: Sexo | None = None
    estatura: str | None = Field(default=None, max_length=10)
    fecha_vista: date | None = None
    lugar: str | None = Field(default=None, min_length=3, max_length=100)
    descripcion: str | None = Field(default=None, min_length=3, max_length=2000)
    senas_particulares: str | None = Field(default=None, max_length=1000)
    vestimenta: str | None = Field(default=None, max_length=1000)
    contacto_nombre: str | None = Field(default=None, min_length=3, max_length=50)
    contacto_telefono: Telefono | None = None
    ubicacion: LatLng | None = None


class EstadoPersonaIn(BaseModel):
    estado: EstadoCasoPersona


class PersonaOut(BaseModel):
    id: UUID
    nombre: str
    edad: int | None
    sexo: str | None
    estatura: str | None
    fecha_vista: date | None
    lugar: str | None
    descripcion: str
    senas_particulares: str | None
    vestimenta: str | None
    estado: EstadoCasoPersona
    es_menor: bool
    # None si no hay foto o si es de un menor y quien consulta no puede verla
    foto_url: str | None
    foto_oculta: bool
    ubicacion: LatLng | None
    # El contacto solo sale en el detalle, nunca en el listado
    contacto_nombre: str | None
    contacto_telefono: str | None
    # La creé yo / la puedo editar y cambiarle el estado (autor o administrador)
    es_mia: bool
    puede_gestionar: bool
    aviso: str | None = None
    encontrado_en: datetime | None
    creado_en: datetime
    actualizado_en: datetime

    @field_validator("ubicacion", mode="before")
    @classmethod
    def _ubicacion(cls, valor):
        if isinstance(valor, WKBElement | WKTElement):
            return latlng_desde_punto(valor)
        return valor
