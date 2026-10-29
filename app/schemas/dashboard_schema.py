"""Dashboard por rol (A7, solo backend: el panel lo conecta Elkin).

Mismo formato que espera `rescate360-web/src/types/dashboard.ts` ({resumen, recientes}),
en snake_case; `hace` ("Hace 5 min") lo calcula el front con `creado_en`.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ResumenOut(BaseModel):
    reportes_pendientes: int
    solicitudes_activas: int
    alertas_activas: int
    centros_registrados: int
    personas_buscando: int
    voluntarios_activos: int
    # Solo voluntario: sus asignaciones activas
    mis_tareas_activas: int | None = None
    # Solo super admin: casos abiertos sin organización que hay que enrutar a mano
    casos_sin_organizacion: int | None = None


class ActividadOut(BaseModel):
    id: UUID
    tipo: Literal["reporte", "solicitud"]
    titulo: str
    detalle: str
    estado: str
    creado_en: datetime


class TotalesOrganizacionOut(BaseModel):
    organizacion_id: UUID
    nombre: str
    reportes_pendientes: int
    solicitudes_activas: int
    voluntarios_activos: int


class DashboardOut(BaseModel):
    alcance: Literal["organizacion", "global"]
    resumen: ResumenOut
    recientes: list[ActividadOut]
    # Solo super admin
    por_organizacion: list[TotalesOrganizacionOut] | None = None
