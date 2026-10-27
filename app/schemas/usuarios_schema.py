from datetime import datetime
from uuid import UUID

from geoalchemy2.elements import WKBElement
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EstadoUsuario, PlataformaDispositivo, RolUsuario, TipoConsentimiento
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.utils.geo import latlng_desde_punto


class UsuarioOut(BaseModel):
    """Usuario tal como lo ven los front (nunca incluye password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    email: str
    telefono: str | None
    rol: RolUsuario
    estado: EstadoUsuario
    organizacion_id: UUID | None
    ultimo_acceso: datetime | None
    creado_en: datetime


class UbicacionOut(BaseModel):
    """Última ubicación conocida del usuario (la usan las alertas por zona)."""

    model_config = ConfigDict(from_attributes=True)

    ubicacion_actual: LatLng | None
    ubicacion_actualizada_en: datetime | None

    @field_validator("ubicacion_actual", mode="before")
    @classmethod
    def _a_latlng(cls, valor):
        # El modelo guarda un punto PostGIS; la API lo expone como {"lat", "lng"}
        if isinstance(valor, WKBElement):
            return latlng_desde_punto(valor)
        return valor


class DispositivoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Token de Firebase Cloud Messaging que entrega la app al iniciar sesión
    token_push: str = Field(min_length=1, max_length=255)
    plataforma: PlataformaDispositivo


class DispositivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    token_push: str
    plataforma: PlataformaDispositivo
    actualizado_en: datetime


class ConsentimientoIn(BaseModel):
    """Dar o retirar una autorización. La de tratamiento de datos se da en el registro."""

    tipo: TipoConsentimiento
    aceptado: bool


class ConsentimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo: TipoConsentimiento
    aceptado: bool
    version_politica: str
    creado_en: datetime
