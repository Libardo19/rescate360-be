"""Schemas del módulo zonas peligrosas. La zona es siempre un círculo: {"lat", "lng", "radio_m"}."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import EstadoZona, NivelZona
from app.utils.geo import latlng_desde_punto

RADIO_MAXIMO_M = 100_000  # 100 km


class ZonaCirculo(BaseModel):
    # cuando este alertas, se crea un app/schemas/geo_schema.py compartido (deuda menor).
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radio_m: float = Field(gt=0, le=RADIO_MAXIMO_M)


class ZonaPeligrosaIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=100)
    tipo_riesgo: str = Field(min_length=1, max_length=60)
    nivel: NivelZona
    descripcion: str | None = Field(default=None, max_length=2000)
    estado: EstadoZona = EstadoZona.ACTIVA
    zona: ZonaCirculo
    # Solo lo puede indicar el super_admin; el administrador usa siempre la suya
    organizacion_id: UUID | None = None


class ZonaPeligrosaPatchIn(BaseModel):
    """Modificación parcial: solo cambia lo que llega. descripcion en null la borra."""

    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    tipo_riesgo: str | None = Field(default=None, min_length=1, max_length=60)
    nivel: NivelZona | None = None
    descripcion: str | None = Field(default=None, max_length=2000)
    estado: EstadoZona | None = None
    zona: ZonaCirculo | None = None

    @model_validator(mode="after")
    def _validar(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para modificar")
        for campo in ("nombre", "tipo_riesgo", "nivel", "estado", "zona"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"El campo {campo} no puede ser nulo")
        return self


class ZonaPeligrosaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    tipo_riesgo: str
    nivel: NivelZona
    descripcion: str | None
    estado: EstadoZona
    zona: ZonaCirculo
    organizacion_id: UUID | None
    gestionado_por: UUID
    actualizado_en: datetime
    # True = es de mi organización (o soy super_admin): puedo editarla
    propia: bool = False
    # Solo si se consultó con lat y lng: metros hasta el borde del círculo (0 si estoy dentro)
    distancia_m: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _armar_zona(cls, valor):
        # El modelo guarda centro (punto PostGIS) y radio_m; la API los expone juntos como "zona"
        if isinstance(valor, dict):
            return valor
        campos = (
            "id", "nombre", "tipo_riesgo", "nivel", "descripcion", "estado",
            "organizacion_id", "gestionado_por", "actualizado_en",
        )
        datos = {campo: getattr(valor, campo) for campo in campos}
        datos["zona"] = {**latlng_desde_punto(valor.centro), "radio_m": valor.radio_m}
        return datos
