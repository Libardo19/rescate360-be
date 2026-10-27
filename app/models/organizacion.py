"""organizaciones — solo super_admin puede crearlas (o el equipo, vía BD)."""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import TipoOrganizacion, pg_enum


class Organizacion(Base):
    __tablename__ = "organizaciones"
    __table_args__ = (
        # Creados en la migración 0003
        Index("ix_organizaciones_zona_cobertura", "zona_cobertura", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[TipoOrganizacion] = mapped_column(pg_enum(TipoOrganizacion, "tipo_organizacion"), nullable=False)
    telefono_contacto: Mapped[str | None] = mapped_column(String(10), nullable=True)
    zona_cobertura: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False), nullable=True
    )
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="organizacion")

    def __repr__(self) -> str:
        return f"<Organizacion {self.id} {self.nombre}>"
