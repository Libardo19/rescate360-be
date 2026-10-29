"""Historial de auditoría (A7). Solo lectura: lo llena el trigger fn_auditoria() de Postgres."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import OperacionAuditoria

# Nombre de la tabla → módulo como lo muestra el panel
MODULOS = {
    "usuarios": "Usuarios",
    "solicitudes_ayuda": "Solicitudes",
    "reportes": "Reportes",
    "personas_desaparecidas": "Desaparecidos",
    "zonas_peligrosas": "Zonas",
    "alertas": "Alertas",
    "consentimientos": "Consentimientos",
    "contactos_emergencia": "Contactos",
}
VERBOS = {OperacionAuditoria.INSERT: "Creó", OperacionAuditoria.UPDATE: "Actualizó", OperacionAuditoria.DELETE: "Eliminó"}


class ActorOut(BaseModel):
    id: UUID
    nombre: str


class AuditoriaOut(BaseModel):
    id: UUID
    tabla: str
    modulo: str
    registro_id: UUID
    operacion: OperacionAuditoria
    # None = el sistema (jobs) o una acción sin sesión, como el registro público
    actor: ActorOut | None
    # "Actualizó Solicitudes (estado, modificado_por)"
    accion: str
    campos_modificados: list[str] | None
    datos_anteriores: dict | None
    datos_nuevos: dict | None
    creado_en: datetime
