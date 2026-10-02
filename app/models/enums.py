"""Enums del dominio, compartidos entre varios modelos.

Cada enum se persiste en PostgreSQL como un tipo nativo (`native_enum`), con el
nombre del enum en la migración. Los valores son en minúsculas y en español:
son los mismos que viajan en la API y en el JWT, así que la base debe hablar el
mismo idioma que el cliente.
"""

from enum import StrEnum
from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E", bound=StrEnum)


def pg_enum(enum_class: type[E], name: str) -> SAEnum:
    """Tipo de columna para un enum, persistiendo el valor y no el nombre del miembro.

    Sin `values_callable`, SQLAlchemy guardaría `SUPER_ADMIN` (el nombre del
    miembro) en lugar de `super_admin` (su valor).
    """
    return SAEnum(
        enum_class,
        name=name,
        values_callable=lambda cls: [miembro.value for miembro in cls],
        validate_strings=True,
    )


class RolUsuario(StrEnum):
    """Rol del usuario. Solo `super_admin` puede no tener organización."""

    CIUDADANO = "ciudadano"
    VOLUNTARIO = "voluntario"
    ADMINISTRADOR = "administrador"
    SUPER_ADMIN = "super_admin"

    @property
    def es_privilegiado(self) -> bool:
        """Roles con permisos de gestión dentro de una organización."""
        return self in (RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN)
