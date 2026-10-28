"""Schemas de centros de ayuda."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EstadoCentro, TipoCentro
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.utils.geo import latlng_desde_punto


TIPOS_CENTRO = tuple(t.value for t in TipoCentro)
ESTADOS_CENTRO = tuple(e.value for e in EstadoCentro)


class CentroAyudaBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=100)
    tipo: str
    estado: str = Field(default=EstadoCentro.ACTIVO.value)
    direccion: str | None = Field(default=None, max_length=200)
    recursos_disponibles: str | None = Field(default=None)

    @field_validator('tipo')
    @classmethod
    def _validar_tipo(cls, valor: str) -> str:
        if valor not in TIPOS_CENTRO:
            raise ValueError('tipo debe ser uno de: ' + ', '.join(TIPOS_CENTRO))
        return valor

    @field_validator('estado')
    @classmethod
    def _validar_estado(cls, valor: str) -> str:
        if valor not in ESTADOS_CENTRO:
            raise ValueError('estado debe ser uno de: ' + ', '.join(ESTADOS_CENTRO))
        return valor


class CentroAyudaIn(CentroAyudaBase):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    organizacion_id: UUID | None = None


class CentroAyudaUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    tipo: str | None = None
    estado: str | None = None
    direccion: str | None = Field(default=None, max_length=200)
    recursos_disponibles: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    organizacion_id: UUID | None = None

    @field_validator('tipo')
    @classmethod
    def _validar_tipo(cls, valor: str | None) -> str | None:
        if valor is None:
            return valor
        if valor not in TIPOS_CENTRO:
            raise ValueError('tipo debe ser uno de: ' + ', '.join(TIPOS_CENTRO))
        return valor

    @field_validator('estado')
    @classmethod
    def _validar_estado(cls, valor: str | None) -> str | None:
        if valor is None:
            return valor
        if valor not in ESTADOS_CENTRO:
            raise ValueError('estado debe ser uno de: ' + ', '.join(ESTADOS_CENTRO))
        return valor


class CentroAyudaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    tipo: str
    estado: str
    direccion: str | None = None
    recursos_disponibles: str | None = None
    gestionado_por: UUID
    organizacion_id: UUID | None = None
    ubicacion: LatLng
    distancia_m: float | None = None

    @classmethod
    def desde_modelo(cls, centro, distancia_m: float | None = None) -> 'CentroAyudaOut':
        datos = {
            'id': centro.id,
            'nombre': centro.nombre,
            'tipo': centro.tipo,
            'estado': centro.estado,
            'direccion': centro.direccion,
            'recursos_disponibles': centro.recursos_disponibles,
            'gestionado_por': centro.gestionado_por,
            'organizacion_id': centro.organizacion_id,
            'ubicacion': latlng_desde_punto(centro.ubicacion),
        }
        if distancia_m is not None:
            datos['distancia_m'] = float(distancia_m)
        return cls(**datos)
