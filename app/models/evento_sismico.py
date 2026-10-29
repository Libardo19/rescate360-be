import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventoSismico(Base):
    """Sismo del feed del USGS o del SGC, o simulado para la demo (migración 0018)."""

    __tablename__ = "eventos_sismicos"
    __table_args__ = (
        Index("ix_eventos_sismicos_epicentro", "epicentro", postgresql_using="gist"),
        Index("ix_eventos_sismicos_ocurrido_en", "ocurrido_en"),
        CheckConstraint("fuente IN ('usgs', 'sgc', 'simulado')", name="chk_eventos_sismicos_fuente"),
        CheckConstraint("magnitud >= 0 AND magnitud <= 10", name="chk_eventos_sismicos_magnitud"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Id del sismo en el feed: hace idempotente la sincronización
    id_externo: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    fuente: Mapped[str] = mapped_column(String(10), nullable=False)
    magnitud: Mapped[float] = mapped_column(Float, nullable=False)
    profundidad_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    lugar: Mapped[str] = mapped_column(String(200), nullable=False)
    epicentro: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    ocurrido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Radio donde se pregunta "¿Estás bien?" y se publica la alerta (crece con la magnitud)
    radio_afectacion_m: Mapped[float] = mapped_column(Float, nullable=False)
    alerta_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("alertas.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<EventoSismico {self.id_externo} M{self.magnitud}>"
