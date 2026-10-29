import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoZona, NivelZona, pg_enum


class ZonaPeligrosa(Base):
    __tablename__ = "zonas_peligrosas"
    __table_args__ = (
        # Creados en la migración 0003
        Index("ix_zonas_peligrosas_organizacion_id", "organizacion_id"),
        Index("ix_zonas_peligrosas_area", "area", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    # Texto libre: la app ofrece opciones rápidas, pero la persona puede escribir otro tipo de riesgo
    tipo_riesgo: Mapped[str] = mapped_column(String(60), nullable=False)
    nivel: Mapped[NivelZona] = mapped_column(
        pg_enum(NivelZona, "nivel_zona"),
        nullable=False, default=NivelZona.MEDIO, server_default=NivelZona.MEDIO.value,
    )
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    # La zona se dibuja como círculo: se guardan centro y radio (lo que el front necesita)
    # y el polígono derivado (para consultas "cerca de" y para el mapa).
    centro: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    radio_m: Mapped[float] = mapped_column(Float, nullable=False)
    area: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False), nullable=False
    )
    estado: Mapped[EstadoZona] = mapped_column(
        pg_enum(EstadoZona, "estado_zona"),
        nullable=False, default=EstadoZona.ACTIVA, server_default=EstadoZona.ACTIVA.value,
    )
    gestionado_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    organizacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ZonaPeligrosa {self.id} {self.nombre} {self.estado}>"
