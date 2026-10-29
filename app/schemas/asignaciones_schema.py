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


class VoluntarioAtencionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str


class AtencionOut(BaseModel):
    """Quién atiende o atendió un caso: la asignación más reciente que no se canceló.

    Va dentro de solicitudes y reportes para el panel y los voluntarios; el ciudadano no la recibe.
    """

    model_config = ConfigDict(from_attributes=True)

    voluntario: VoluntarioAtencionOut
    # activa = lo está atendiendo; finalizada = ya lo atendió
    estado: EstadoAsignacion
    desde: datetime
    hasta: datetime | None

    @classmethod
    def desde_asignacion(cls, asignacion) -> "AtencionOut | None":
        if asignacion is None:
            return None
        return cls(
            voluntario=VoluntarioAtencionOut.model_validate(asignacion.voluntario),
            estado=asignacion.estado_asignacion,
            desde=asignacion.asignado_en,
            hasta=asignacion.cerrada_en,
        )
