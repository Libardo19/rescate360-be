"""Schemas de alertas (B3). La alerta es un círculo, igual que las zonas: {"lat", "lng", "radio_m"}."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import EstadoAlerta, NivelAlerta
from app.utils.geo import latlng_desde_punto

RADIO_MAXIMO_M = 300_000  # 300 km: lo que cubre un sismo fuerte
HORAS_POR_DEFECTO = 24
HORAS_MAXIMAS = 168  # una semana


class CirculoAlerta(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radio_m: float = Field(gt=0, le=RADIO_MAXIMO_M)


class AlertaIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str = Field(min_length=3, max_length=100)
    # Texto libre con sugerencias en el panel: inundacion, deslizamiento, seguridad, clima, sismo, otro
    tipo: str = Field(min_length=3, max_length=30)
    mensaje: str = Field(min_length=3, max_length=2000)
    nivel: NivelAlerta = NivelAlerta.MEDIO
    zona: CirculoAlerta
    horas_vigencia: int = Field(default=HORAS_POR_DEFECTO, ge=1, le=HORAS_MAXIMAS)
    # Solo la elige el super admin; el administrador publica siempre en su organización
    organizacion_id: UUID | None = None


class AlertaCambiosIn(BaseModel):
    """Solo cambia lo que llega. `horas_vigencia` vuelve a contar desde ahora."""

    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str | None = Field(default=None, min_length=3, max_length=100)
    mensaje: str | None = Field(default=None, min_length=3, max_length=2000)
    nivel: NivelAlerta | None = None
    horas_vigencia: int | None = Field(default=None, ge=1, le=HORAS_MAXIMAS)

    @model_validator(mode="after")
    def _validar(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para modificar")
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"El campo {campo} no puede ser nulo")
        return self


class AlertaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    titulo: str
    tipo: str
    mensaje: str
    nivel: NivelAlerta
    estado: EstadoAlerta
    origen: str
    zona: CirculoAlerta
    expira_en: datetime
    creado_en: datetime
    actualizado_en: datetime
    organizacion_id: UUID | None
    # True = la puedo editar o cancelar (administrador de su organización o super admin)
    propia: bool = False

    @model_validator(mode="before")
    @classmethod
    def _armar_zona(cls, valor):
        if isinstance(valor, dict):
            return valor
        campos = (
            "id", "titulo", "tipo", "mensaje", "nivel", "estado", "origen",
            "expira_en", "creado_en", "actualizado_en", "organizacion_id",
        )
        datos = {campo: getattr(valor, campo) for campo in campos}
        datos["zona"] = {**latlng_desde_punto(valor.centro), "radio_m": valor.radio_m}
        return datos
