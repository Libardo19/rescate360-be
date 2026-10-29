import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoCheckIn, pg_enum


class CheckIn(Base):
    """El "¿Estás bien?" con vencimiento (migración 0019)."""

    __tablename__ = "check_ins"
    __table_args__ = (
        # Máximo un check-in pendiente por persona
        Index(
            "uq_check_in_pendiente_por_usuario", "usuario_id", unique=True,
            postgresql_where=text("estado = 'pendiente'"),
        ),
        Index("ix_check_ins_evento_sismico_id", "evento_sismico_id"),
        Index("ix_check_ins_estado_vence_en", "estado", "vence_en"),
        CheckConstraint("motivo IN ('sismo', 'manual')", name="chk_check_ins_motivo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    evento_sismico_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eventos_sismicos.id"), nullable=True
    )
    # sismo (lo abrió un sismo cerca) o manual ("modo emergencia" que activó la persona)
    motivo: Mapped[str] = mapped_column(String(10), nullable=False)
    estado: Mapped[EstadoCheckIn] = mapped_column(
        pg_enum(EstadoCheckIn, "estado_check_in"),
        nullable=False, default=EstadoCheckIn.PENDIENTE, server_default=EstadoCheckIn.PENDIENTE.value,
    )
    ultima_ubicacion: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    vence_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    respondido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # El SOS que se creó si respondió "necesito ayuda"
    solicitud_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solicitudes_ayuda.id"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<CheckIn {self.id} {self.usuario_id} {self.estado}>"
