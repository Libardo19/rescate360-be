"""Schemas de reportes de incidentes (A4).

El tipo es texto libre a propósito: hay una lista sugerida, pero si la emergencia no está
en la lista el usuario escribe cuál ("fuga de gas", "árbol caído"…).
"""

import re
import unicodedata
from datetime import datetime
from uuid import UUID

from geoalchemy2.elements import WKBElement, WKTElement
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EstadoReporte, PrioridadSolicitud
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.utils.geo import latlng_desde_punto

# Lista sugerida: valor guardado → etiqueta que muestran la app y el panel
TIPOS_REPORTE: dict[str, str] = {
    "accidente": "Accidente",
    "robo": "Robo",
    "inundacion": "Inundación",
    "deslizamiento": "Deslizamiento",
    "incendio": "Incendio",
    "sismo": "Sismo",
}
# Valor especial del filtro: "todo lo que no está en la lista"
FILTRO_OTROS = "otros"
MAXIMO_ADJUNTOS = 5

_TIPO_VALIDO = re.compile(r"^[a-z0-9áéíóúüñ ]{3,30}$")


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar_tipo(valor: str) -> str:
    """Recorta, colapsa espacios y pasa a minúsculas. Si coincide con uno de la lista
    (sin importar tildes ni mayúsculas) devuelve el de la lista: "Inundación" → "inundacion"."""
    limpio = " ".join(valor.split()).lower()
    if not _TIPO_VALIDO.match(limpio):
        raise ValueError("El tipo debe tener entre 3 y 30 caracteres: solo letras, números y espacios")
    base = _sin_tildes(limpio)
    for clave in TIPOS_REPORTE:
        if base == clave:
            return clave
    return limpio


def etiqueta_tipo(tipo: str) -> str:
    return TIPOS_REPORTE.get(tipo, tipo.capitalize())


class TipoReporteOut(BaseModel):
    valor: str
    etiqueta: str


class ReporteIn(BaseModel):
    """Campos del formulario multipart de POST /reportes (los archivos van aparte)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tipo: str
    descripcion: str = Field(min_length=3, max_length=2000)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    direccion: str | None = Field(default=None, max_length=50)

    @field_validator("tipo")
    @classmethod
    def _tipo(cls, valor: str) -> str:
        return normalizar_tipo(valor)

    @field_validator("direccion")
    @classmethod
    def _direccion(cls, valor: str | None) -> str | None:
        return valor or None


class RechazoIn(BaseModel):
    motivo: str | None = Field(default=None, max_length=200)


class DuplicadoIn(BaseModel):
    duplicado_de_id: UUID


class ReportePrioridadIn(BaseModel):
    prioridad_manual: PrioridadSolicitud

    @field_validator("prioridad_manual")
    @classmethod
    def _no_pendiente(cls, valor: PrioridadSolicitud) -> PrioridadSolicitud:
        if valor == PrioridadSolicitud.PENDIENTE:
            raise ValueError("Elige una prioridad: baja, media, alta o crítica")
        return valor


class ReporteOrganizacionIn(BaseModel):
    organizacion_id: UUID


class EvidenciaOut(BaseModel):
    id: UUID
    tipo: str
    url: str
    mime: str


class ReportanteOut(BaseModel):
    id: UUID
    nombre: str


class ReporteOut(BaseModel):
    id: UUID
    usuario_id: UUID
    tipo: str
    tipo_etiqueta: str
    descripcion: str
    direccion: str | None
    ubicacion: LatLng
    estado: EstadoReporte
    # Sugerencia de la IA (o de las reglas); la prioridad manual del admin prevalece
    prioridad_ia: PrioridadSolicitud
    prioridad_manual: PrioridadSolicitud | None
    confianza_ia: float | None
    razonamiento_ia: str | None
    organizacion_objetivo_id: UUID | None
    organizacion_manual_id: UUID | None
    verificado_por: UUID | None
    verificado_en: datetime | None
    motivo_rechazo: str | None
    duplicado_de_id: UUID | None
    evidencias: list[EvidenciaOut]
    # Solo para quien lo creó, su organización y el super admin: en un reporte verificado
    # que ve cualquiera, no se expone quién lo hizo
    reportante: ReportanteOut | None
    creado_en: datetime
    actualizado_en: datetime

    @field_validator("ubicacion", mode="before")
    @classmethod
    def _ubicacion(cls, valor):
        if isinstance(valor, WKBElement | WKTElement):
            return latlng_desde_punto(valor)
        return valor
