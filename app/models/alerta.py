import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoAlerta, NivelAlerta, pg_enum


class Alerta(Base):
    __tablename__ = "alertas"
    __table_args__ = (
        # Creado en la migración 0003
        Index("ix_alertas_organizacion_id", "organizacion_id"),
        Index("ix_alertas_zona_afectada", "zona_afectada", postgresql_using="gist"),
        # Migración 0017
        Index("ix_alertas_estado_expira_en", "estado", "expira_en"),
        CheckConstraint("radio_m > 0 AND radio_m <= 300000", name="chk_alertas_radio"),
        CheckConstraint("origen IN ('manual', 'sismo')", name="chk_alertas_origen"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    titulo: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    nivel: Mapped[NivelAlerta] = mapped_column(
        pg_enum(NivelAlerta, "nivel_alerta"),
        nullable=False, default=NivelAlerta.MEDIO, server_default=NivelAlerta.MEDIO.value,
    )
    estado: Mapped[EstadoAlerta] = mapped_column(
        pg_enum(EstadoAlerta, "estado_alerta"),
        nullable=False, default=EstadoAlerta.ACTIVA, server_default=EstadoAlerta.ACTIVA.value,
    )
    # manual (la crea un administrador) o sismo (la crea el job de sismos)
    origen: Mapped[str] = mapped_column(String(10), nullable=False, default="manual", server_default="manual")
    # Círculo, como las zonas: centro + radio; zona_afectada es el polígono derivado
    centro: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    radio_m: Mapped[float] = mapped_column(Float, nullable=False)
    zona_afectada: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False), nullable=False
    )
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creado_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    organizacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Alerta {self.id} {self.titulo} {self.estado}>"
