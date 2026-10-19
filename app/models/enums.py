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
    SOS = "sos"


class PrioridadSolicitud(str, enum.Enum):
    PENDIENTE = "pendiente"
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class EstadoSolicitud(str, enum.Enum):
    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    ATENDIDA = "atendida"
    CANCELADA = "cancelada"


class TipoSolicitud(str, enum.Enum):
    MEDICA = "medica"
    ALIMENTARIA = "alimentaria"
    REFUGIO = "refugio"
    RESCATE = "rescate"
    ROPA = "ropa"
    OTRO = "otro"


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
