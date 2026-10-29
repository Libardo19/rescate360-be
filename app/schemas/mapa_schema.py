"""Schemas del mapa en vivo: un solo formato de punto para la app y el panel."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

CapaMapa = Literal["solicitudes", "reportes", "centros", "zonas", "alertas"]
CAPAS_MAPA: tuple[str, ...] = ("solicitudes", "reportes", "centros", "zonas", "alertas", "sismos")
CAPAS_POR_DEFECTO = "solicitudes,reportes"


class PuntoMapa(BaseModel):
    id: UUID
    capa: Literal["solicitud", "reporte", "centro", "zona", "alerta", "sismo"]
    tipo: str
    titulo: str
    detalle: str
    estado: str
    prioridad: str | None = None
    lat: float
    lng: float
    # Zonas, alertas y sismos se dibujan como círculo
    radio_m: float | None = None
    # True = la posición está redondeada (~200 m) porque el caso es de otra persona u organización
    aproximada: bool
    # True = puedo actuar sobre él según el módulo y mis permisos
    propio: bool
    # False = se cerró. En el polling con `desde`, el cliente lo quita del mapa
    activo: bool
    actualizado_en: datetime


class MapaOut(BaseModel):
    puntos: list[PuntoMapa]
    # El cliente lo manda como `desde` en la siguiente consulta del polling
    generado_en: datetime
