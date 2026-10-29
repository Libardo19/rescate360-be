"""Schemas de campañas y donaciones (B5). La app no procesa pagos: solo se registran."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import EstadoDonacion

Categoria = Literal["alimentos", "ropa", "medicamentos", "agua", "dinero", "otro"]


class CampanaIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str = Field(min_length=3, max_length=100)
    descripcion: str = Field(min_length=3, max_length=2000)
    categoria: Categoria
    meta: float = Field(gt=0)
    unidad: str = Field(min_length=1, max_length=20)
    fecha_fin: date
    # Solo la elige el super admin; el administrador la crea en su organización
    organizacion_id: UUID | None = None

    @model_validator(mode="after")
    def _fecha(self):
        if self.fecha_fin < date.today():
            raise ValueError("La fecha de cierre no puede estar en el pasado")
        return self


class CampanaCambiosIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str | None = Field(default=None, min_length=3, max_length=100)
    descripcion: str | None = Field(default=None, min_length=3, max_length=2000)
    meta: float | None = Field(default=None, gt=0)
    fecha_fin: date | None = None
    activa: bool | None = None

    @model_validator(mode="after")
    def _validar(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para modificar")
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"El campo {campo} no puede ser nulo")
        return self


class CampanaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    titulo: str
    descripcion: str
    categoria: str
    meta: float
    unidad: str
    fecha_fin: date
    activa: bool
    organizacion_id: UUID | None
    creado_en: datetime
    # Suma de sus donaciones (cantidad; en dinero, el monto)
    recaudado: float = 0
    propia: bool = False


class DonacionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    categoria: Categoria
    descripcion: str | None = Field(default=None, max_length=200)
    cantidad: int = Field(gt=0)
    unidad: str = Field(min_length=1, max_length=20)
    monto: float | None = Field(default=None, gt=0)
    campana_id: UUID | None = None
    centro_id: UUID | None = None

    @model_validator(mode="after")
    def _monto(self):
        if self.categoria == "dinero" and self.monto is None:
            raise ValueError("Una donación en dinero necesita el monto")
        if self.categoria != "dinero" and self.monto is not None:
            raise ValueError("El monto solo aplica a donaciones en dinero")
        return self


class DonacionEstadoIn(BaseModel):
    estado: EstadoDonacion


class DonacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    categoria: str
    descripcion: str | None
    cantidad: int
    unidad: str
    monto: float | None
    estado: EstadoDonacion
    campana_id: UUID | None
    centro_id: UUID | None
    organizacion_id: UUID | None
    creado_en: datetime
