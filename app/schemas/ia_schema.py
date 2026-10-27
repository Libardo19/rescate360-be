"""Lo que entra y sale del clasificador (Gemini o reglas). Igual para solicitudes y reportes."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import PrioridadSolicitud


class CasoIA(BaseModel):
    """Todo lo que la IA analiza de un caso."""

    clase: Literal["solicitud", "reporte"]
    tipo: str
    descripcion: str
    direccion: str | None = None
    origen: str = "manual"
    evidencias: int = 0  # fotos y videos adjuntos (solo reportes)


class OrganizacionIA(BaseModel):
    id: UUID
    nombre: str
    tipo: str


class ClasificacionIA(BaseModel):
    """Sugerencia final: el administrador la puede corregir (prioridad manual, organización manual)."""

    prioridad: PrioridadSolicitud
    confianza: float = Field(ge=0.0, le=1.0)
    razonamiento: str = Field(min_length=10, max_length=500)
    organizacion_id: UUID | None = None
    fuente: str  # "gemini:<modelo>" o "reglas"

    @field_validator("prioridad")
    @classmethod
    def _no_pendiente(cls, valor: PrioridadSolicitud) -> PrioridadSolicitud:
        if valor == PrioridadSolicitud.PENDIENTE:
            raise ValueError("La clasificación debe dar una prioridad real")
        return valor
