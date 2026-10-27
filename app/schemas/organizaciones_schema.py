from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TipoOrganizacion
from app.schemas.usuarios_schema import normalizar_nombre
from app.utils.telefono import Telefono


class OrganizacionIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    tipo: TipoOrganizacion
    telefono_contacto: Telefono | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        return normalizar_nombre(valor)


class OrganizacionCambiosIn(BaseModel):
    """Solo se aplican los campos enviados. `activa=false` deja sin acceso a su gente."""

    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    tipo: TipoOrganizacion | None = None
    telefono_contacto: Telefono | None = None
    activa: bool | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str | None) -> str | None:
        return normalizar_nombre(valor) if valor is not None else None


class OrganizacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    tipo: TipoOrganizacion
    telefono_contacto: str | None
    activa: bool
    creado_en: datetime
