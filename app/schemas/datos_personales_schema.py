"""Derechos del titular (Ley 1581 de 2012): conocer y suprimir sus datos personales (A6)."""

from datetime import datetime
from uuid import UUID

from geoalchemy2.elements import WKBElement, WKTElement
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    EstadoCasoPersona,
    EstadoReporte,
    EstadoSolicitud,
    OrigenSolicitud,
    PlataformaDispositivo,
    TipoSolicitud,
)
from app.schemas.contactos_emergencia_schema import ContactoOut
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.schemas.usuarios_schema import ConsentimientoOut, UsuarioOut
from app.utils.geo import latlng_desde_punto


class _DeORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MiUbicacionOut(_DeORM):
    ubicacion_actual: LatLng | None
    ubicacion_actualizada_en: datetime | None

    @field_validator("ubicacion_actual", mode="before")
    @classmethod
    def _ubicacion(cls, valor):
        if isinstance(valor, WKBElement | WKTElement):
            return latlng_desde_punto(valor)
        return valor


class MiDispositivoOut(_DeORM):
    plataforma: PlataformaDispositivo
    creado_en: datetime


class MiSolicitudOut(_DeORM):
    id: UUID
    tipo: TipoSolicitud
    origen: OrigenSolicitud
    estado: EstadoSolicitud
    descripcion: str
    direccion: str | None
    creado_en: datetime


class MiReporteOut(_DeORM):
    id: UUID
    tipo: str
    estado: EstadoReporte
    descripcion: str
    direccion: str | None
    creado_en: datetime


class MiPersonaReportadaOut(_DeORM):
    id: UUID
    nombre: str
    estado_caso: EstadoCasoPersona
    creado_en: datetime


class MisDatosOut(BaseModel):
    """Todo lo que RESCATE360 guarda de la persona. El panel/la app lo ofrece para descargar."""

    perfil: UsuarioOut
    ubicacion: MiUbicacionOut
    consentimientos: list[ConsentimientoOut]
    contactos_emergencia: list[ContactoOut]
    dispositivos: list[MiDispositivoOut]
    solicitudes: list[MiSolicitudOut]
    reportes: list[MiReporteOut]
    personas_reportadas: list[MiPersonaReportadaOut]
    generado_en: datetime


class EliminarCuentaIn(BaseModel):
    """Se pide la contraseña para que nadie borre la cuenta con un teléfono prestado."""

    password: str = Field(min_length=1)
