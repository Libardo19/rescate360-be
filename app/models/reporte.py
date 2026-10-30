import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EstadoReporte, PrioridadSolicitud, pg_enum
from app.models.evidencia_reporte import EvidenciaReporte


class Reporte(Base):
    __tablename__ = "reportes"
    __table_args__ = (
        # Creados en la migración 0003
        Index("ix_reportes_estado", "estado"),
        Index("ix_reportes_ubicacion", "ubicacion", postgresql_using="gist"),
        # Migración 0010
        Index("ix_reportes_tipo", "tipo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    # Texto libre a propósito: lista sugerida en GET /reportes/tipos + "otro" escrito por el usuario
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ubicacion: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    estado: Mapped[EstadoReporte] = mapped_column(
        pg_enum(EstadoReporte, "estado_reporte"),
        nullable=False, default=EstadoReporte.PENDIENTE, server_default=EstadoReporte.PENDIENTE.value,
    )
    verificado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True
    )
    verificado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_rechazo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duplicado_de_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reportes.id"), nullable=True
    )
    organizacion_objetivo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )
    # Clasificación de la IA (migración 0012). La prioridad manual del admin prevalece.
    prioridad_ia: Mapped[PrioridadSolicitud] = mapped_column(
        pg_enum(PrioridadSolicitud, "prioridad_solicitud"),
        nullable=False, default=PrioridadSolicitud.PENDIENTE, server_default=PrioridadSolicitud.PENDIENTE.value,
    )
    prioridad_manual: Mapped[PrioridadSolicitud | None] = mapped_column(
        pg_enum(PrioridadSolicitud, "prioridad_solicitud"), nullable=True
    )
    confianza_ia: Mapped[float | None] = mapped_column(Float, nullable=True)
    razonamiento_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    # El super admin enruta a mano; prevalece sobre la sugerencia de la IA (migración 0010)
    organizacion_manual_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    evidencias: Mapped[list[EvidenciaReporte]] = relationship(
        lazy="selectin", order_by=EvidenciaReporte.creado_en, cascade="all, delete-orphan", passive_deletes=True
    )
    autor: Mapped["Usuario"] = relationship(foreign_keys=[usuario_id], lazy="selectin")

    # Asignaciones del caso, para saber quién lo atiende (se cargan en lote con la consulta)
    asignaciones: Mapped[list["Asignacion"]] = relationship(viewonly=True, lazy="selectin")

    @property
    def atencion(self) -> "Asignacion | None":
        """La asignación más reciente que no se canceló: quién lo atiende o lo atendió."""
        vigentes = [a for a in self.asignaciones if a.estado_asignacion.value != "cancelada"]
        return max(vigentes, key=lambda a: a.asignado_en) if vigentes else None

    def __repr__(self) -> str:
        return f"<Reporte {self.id} {self.tipo} {self.estado}>"
