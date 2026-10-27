from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import EstadoAsignacion


class AsignacionEstadoIn(BaseModel):
    """Una asignación solo se cierra: finalizada o cancelada."""

    estado: EstadoAsignacion

    @field_validator("estado")
    @classmethod
    def _solo_cierre(cls, valor: EstadoAsignacion) -> EstadoAsignacion:
        if valor == EstadoAsignacion.ACTIVA:
            raise ValueError("El estado debe ser finalizada o cancelada")
        return valor


class AsignacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    solicitud_id: UUID | None
    reporte_id: UUID | None
    voluntario_id: UUID
    estado_asignacion: EstadoAsignacion
    asignado_en: datetime
