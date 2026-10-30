"""Schemas del módulo solicitudes_ayuda.

La API habla en {"lat", "lng"}; la conversión a PostGIS vive solo en app/utils/geo.py.
"""

from datetime import datetime
from uuid import UUID

from geoalchemy2.elements import WKBElement
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.enums import EstadoSolicitud, OrigenSolicitud, PrioridadSolicitud, TipoSolicitud
from app.schemas.asignaciones_schema import AtencionOut
from app.utils.geo import latlng_desde_punto


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SolicitudAyudaIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    descripcion: str = Field(min_length=3, max_length=2000)
    tipo: TipoSolicitud
    ubicacion: LatLng
    direccion: str | None = Field(default=None, max_length=50)


class SolicitudSOSIn(BaseModel):
    """El botón SOS solo manda la ubicación: todo lo demás lo decide el backend."""

    ubicacion: LatLng


class SolicitudPrioridadIn(BaseModel):
    prioridad_manual: PrioridadSolicitud

    @field_validator("prioridad_manual")
    @classmethod
    def _no_pendiente(cls, valor: PrioridadSolicitud) -> PrioridadSolicitud:
        if valor == PrioridadSolicitud.PENDIENTE:
            raise ValueError("La prioridad manual debe ser baja, media, alta o crítica")
        return valor


class SolicitudEstadoIn(BaseModel):
    estado: EstadoSolicitud


class SolicitudOrganizacionIn(BaseModel):
    """El super admin enruta la solicitud a mano (prevalece sobre la sugerencia de la IA)."""

    organizacion_id: UUID


class SolicitanteOut(BaseModel):
    """Datos de contacto de quien pidió la ayuda. Solo los ven el propio ciudadano, la
    organización que atiende el caso y el super admin (el detalle ya exige ese alcance)."""

    model_config = ConfigDict(from_attributes=True)

    nombre: str
    telefono: str | None


class SolicitudAyudaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    descripcion: str
    direccion: str | None
    tipo: TipoSolicitud
    ubicacion: LatLng
    origen: OrigenSolicitud
    prioridad_ia: PrioridadSolicitud
    prioridad_manual: PrioridadSolicitud | None
    organizacion_objetivo_id: UUID | None
    organizacion_manual_id: UUID | None
    confianza_ia: float | None
    razonamiento_ia: str | None
    estado: EstadoSolicitud
    solicitante: SolicitanteOut | None = None
    # Quién la atiende o la atendió (solo para la organización y el super admin)
    atencion: AtencionOut | None = None
    creado_en: datetime
    actualizado_en: datetime

    @field_validator("atencion", mode="before")
    @classmethod
    def _atencion(cls, valor):
        # Desde el ORM llega la asignación (Solicitud.atencion); se expone como AtencionOut
        if valor is None or isinstance(valor, AtencionOut | dict):
            return valor
        return AtencionOut.desde_asignacion(valor)

    @field_validator("ubicacion", mode="before")
    @classmethod
    def _ubicacion_a_latlng(cls, valor):
        # El modelo guarda un punto PostGIS; la API lo expone como {"lat", "lng"}
        if isinstance(valor, WKBElement):
            return latlng_desde_punto(valor)
        # Soportar objetos Shapely
        if hasattr(valor, "geom_type") and valor.geom_type == "Point":
            try:
                return {"lat": valor.y, "lng": valor.x}
            except Exception:
                pass
        if hasattr(valor, "y") and hasattr(valor, "x") and not isinstance(valor, dict):
            try:
                return {"lat": valor.y, "lng": valor.x}
            except Exception:
                pass
        if isinstance(valor, (bytes, memoryview)):
            try:
                return latlng_desde_punto(WKBElement(valor))
            except Exception:
                pass
        return valor

    @computed_field
    @property
    def prioridad_efectiva(self) -> PrioridadSolicitud:
        """La prioridad manual del administrador prevalece sobre la de la IA."""
        return self.prioridad_manual if self.prioridad_manual is not None else self.prioridad_ia

    @computed_field
    @property
    def organizacion_efectiva_id(self) -> UUID | None:
        """La organización asignada a mano prevalece sobre la sugerida por la IA."""
        if self.organizacion_manual_id is not None:
            return self.organizacion_manual_id
        return self.organizacion_objetivo_id
