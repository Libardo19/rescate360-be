"""Schemas de sismos y del "¿Estás bien?" (check-ins)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from geoalchemy2.elements import WKBElement, WKTElement
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import EstadoCheckIn
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.utils.geo import latlng_desde_punto

AVISO_SISMOS = (
    "Información de fuentes sismológicas públicas (USGS/SGC); no es una alerta temprana oficial. "
    "Sigue las indicaciones del Servicio Geológico Colombiano y de la UNGRD."
)
# Valledupar: donde cae el sismo simulado de la demo si no se indica otro punto
VALLEDUPAR = (10.4631, -73.2532)


def _a_latlng(valor):
    if isinstance(valor, WKBElement | WKTElement):
        return latlng_desde_punto(valor)
    return valor


class SismoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fuente: str
    magnitud: float
    profundidad_km: float | None
    lugar: str
    epicentro: LatLng
    ocurrido_en: datetime
    radio_afectacion_m: float
    alerta_id: UUID | None
    # Solo si conozco la ubicación del usuario: metros desde su posición hasta el epicentro
    distancia_m: float | None = None
    aviso: str = AVISO_SISMOS

    @field_validator("epicentro", mode="before")
    @classmethod
    def _epicentro(cls, valor):
        return _a_latlng(valor)


class SismoSimuladoIn(BaseModel):
    """Para la demo y las pruebas: por defecto un M5.2 en Valledupar."""

    lat: float = Field(default=VALLEDUPAR[0], ge=-90, le=90)
    lng: float = Field(default=VALLEDUPAR[1], ge=-180, le=180)
    magnitud: float = Field(default=5.2, ge=1, le=9.5)
    profundidad_km: float = Field(default=10, ge=0, le=700)
    lugar: str = Field(default="Simulacro · Valledupar, Cesar", min_length=3, max_length=200)


class CheckInManualIn(BaseModel):
    """"Modo emergencia": la persona pide que le pregunten si está bien en unos minutos."""

    ubicacion: LatLng | None = None


class RespuestaCheckInIn(BaseModel):
    estado: Literal["a_salvo", "necesito_ayuda"]
    ubicacion: LatLng | None = None


class CheckInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    motivo: str
    estado: EstadoCheckIn
    evento_sismico_id: UUID | None
    ultima_ubicacion: LatLng | None
    vence_en: datetime
    respondido_en: datetime | None
    solicitud_id: UUID | None
    creado_en: datetime

    @field_validator("ultima_ubicacion", mode="before")
    @classmethod
    def _ubicacion(cls, valor):
        return _a_latlng(valor)


class PersonaCheckInOut(CheckInOut):
    """Para el panel: quién es y cómo está."""

    usuario_id: UUID
    nombre: str
    telefono: str | None


class ResumenCheckInsOut(BaseModel):
    pendiente: int = 0
    a_salvo: int = 0
    necesito_ayuda: int = 0
    sin_respuesta: int = 0


class CheckInsEventoOut(BaseModel):
    resumen: ResumenCheckInsOut
    personas: list[PersonaCheckInOut]

    @model_validator(mode="after")
    def _ordenar(self):
        # Primero quien pidió ayuda, luego quien no respondió
        orden = {"necesito_ayuda": 0, "sin_respuesta": 1, "pendiente": 2, "a_salvo": 3}
        self.personas.sort(key=lambda p: orden[p.estado.value])
        return self
