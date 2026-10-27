import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoAsignacion, pg_enum


class Asignacion(Base):
    __tablename__ = "asignaciones"
    __table_args__ = (
        CheckConstraint(
            "(solicitud_id IS NOT NULL AND reporte_id IS NULL) OR "
            "(solicitud_id IS NULL AND reporte_id IS NOT NULL)",
            name="chk_asignacion_a_uno_solo",
        ),
        # Creados en la migración 0007: un voluntario no tiene dos asignaciones activas al mismo caso
        Index(
            "uq_asignacion_activa_solicitud", "voluntario_id", "solicitud_id", unique=True,
            postgresql_where=text("solicitud_id IS NOT NULL AND estado_asignacion = 'activa'"),
        ),
        Index(
            "uq_asignacion_activa_reporte", "voluntario_id", "reporte_id", unique=True,
            postgresql_where=text("reporte_id IS NOT NULL AND estado_asignacion = 'activa'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    solicitud_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solicitudes_ayuda.id"), nullable=True
    )
    reporte_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reportes.id"), nullable=True
    )
    voluntario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    asignado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    estado_asignacion: Mapped[EstadoAsignacion] = mapped_column(
        pg_enum(EstadoAsignacion, "estado_asignacion"),
        nullable=False, default=EstadoAsignacion.ACTIVA, server_default=EstadoAsignacion.ACTIVA.value,
    )

    def __repr__(self) -> str:
        return f"<Asignacion {self.id} voluntario={self.voluntario_id}>"
