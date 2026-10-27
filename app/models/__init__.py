"""Modelos de la aplicación.

Todo modelo debe importarse en este `__init__`: `migrations/env.py` hace
`import app.models` para llenar `Base.metadata`, y un modelo que no se importe
no aparece en el metadata. El síntoma es que `alembic --autogenerate` propone
`drop_table` de las tablas que no importó.
"""

from app.models.usuario import Usuario
from app.models.organizacion import Organizacion
from app.models.contacto_emergencia import ContactoEmergencia
from app.models.reporte import Reporte
from app.models.evidencia_reporte import EvidenciaReporte
from app.models.persona_desaparecida import PersonaDesaparecida
from app.models.solicitud_ayuda import SolicitudAyuda
from app.models.centro_ayuda import CentroAyuda
from app.models.alerta import Alerta
from app.models.zona_peligrosa import ZonaPeligrosa
from app.models.donacion import Donacion
from app.models.guia_emergencia import GuiaEmergencia
from app.models.cola_alerta_offline import ColaAlertaOffline
from app.models.auditoria import Auditoria
from app.models.asignacion import Asignacion
from app.models.consentimiento import Consentimiento
from app.models.dispositivo import Dispositivo
#from app.models.perfil_voluntario import PerfilVoluntario


__all__ = [
    "Usuario",
    "Organizacion",
    "ContactoEmergencia",
    "Reporte",
    "EvidenciaReporte",
    "PersonaDesaparecida",
    "SolicitudAyuda",
    "CentroAyuda",
    "Alerta",
    "ZonaPeligrosa",
    "Donacion",
    "GuiaEmergencia",
    "ColaAlertaOffline",
    "Auditoria",
    "Asignacion",
    "Consentimiento",
    "Dispositivo",
    #"PerfilVoluntario",
]