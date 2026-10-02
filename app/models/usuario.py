"""Modelo de `usuarios` (migración 0002).

`organizacion_id` todavía no está: es nullable y lo agrega la migración 0016
junto con la tabla `organizaciones`. No se declara acá antes para que el
autogenerate de 0002 no intente crear una FK a una tabla que aún no existe.
Los índices espaciales de `ubicacion_actual` tampoco van acá: son de la
migración 0013_indices_busqueda.
"""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import RolUsuario, pg_enum


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    rol: Mapped[RolUsuario] = mapped_column(
        pg_enum(RolUsuario, "rol_usuario"),
        nullable=False,
        default=RolUsuario.CIUDADANO,
        server_default=RolUsuario.CIUDADANO.value,
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    # Último punto reportado por la app. Lo usan `notificar_voluntarios_cercanos`
    # y `limpiar_datos_retencion` (RETENCION_UBICACIONES_DIAS).
    ubicacion_actual: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=True,
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f""