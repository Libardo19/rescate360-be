import enum

from sqlalchemy import Enum as SQLAlchemyEnum


def pg_enum(enum_cls: type[enum.Enum], pg_name: str) -> SQLAlchemyEnum:
    return SQLAlchemyEnum(
        enum_cls, name=pg_name,
        values_callable=lambda e: [member.value for member in e],
    )


class RolUsuario(str, enum.Enum):
    CIUDADANO = "ciudadano"
    VOLUNTARIO = "voluntario"
    ADMINISTRADOR = "administrador"
    SUPER_ADMIN = "super_admin"


class TipoOrganizacion(str, enum.Enum):
    BOMBEROS = "bomberos"
    POLICIA = "policia"
    CRUZ_ROJA = "cruz_roja"
    DEFENSA_CIVIL = "defensa_civil"
    ONG = "ong"
    OTRO = "otro"


class EstadoReporte(str, enum.Enum):
    PENDIENTE = "pendiente"
    VERIFICADO = "verificado"
    RECHAZADO = "rechazado"
    DUPLICADO = "duplicado"
    NO_VERIFICABLE = "no_verificable"


class EstadoCasoPersona(str, enum.Enum):
    BUSCANDO = "buscando"
    ENCONTRADO = "encontrado"


class OrigenSolicitud(str, enum.Enum):
    MANUAL = "manual"
    ACELEROMETRO = "acelerometro"


class PrioridadSolicitud(str, enum.Enum):
    PENDIENTE = "pendiente"
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class EstadoSolicitud(str, enum.Enum):
    PENDIENTE = "pendiente"
    EN_ATENCION = "en_atencion"
    RESUELTA = "resuelta"


class EstadoZona(str, enum.Enum):
    ACTIVA = "activa"
    RESUELTA = "resuelta"


class MetodoEnvio(str, enum.Enum):
    SMS = "sms"
    MESH = "mesh"
    LOCAL = "local"


class OperacionAuditoria(str, enum.Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class EstadoAsignacion(str, enum.Enum):
    ACTIVA = "activa"
    FINALIZADA = "finalizada"
    CANCELADA = "cancelada"


# --- Dev A: usuarios, consentimientos y dispositivos (migración 0005) ---


class EstadoUsuario(str, enum.Enum):
    ACTIVO = "activo"
    EN_ESPERA = "en_espera"
    BLOQUEADO = "bloqueado"


class TipoConsentimiento(str, enum.Enum):
    TRATAMIENTO_DATOS = "tratamiento_datos"
    UBICACION = "ubicacion"
    FOTO_PERSONA = "foto_persona"


class PlataformaDispositivo(str, enum.Enum):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"
