import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoSolicitud, OrigenSolicitud, PrioridadSolicitud, TipoSolicitud, pg_enum


class SolicitudAyuda(Base):
    __tablename__ = "solicitudes_ayuda"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[TipoSolicitud] = mapped_column(
        pg_enum(TipoSolicitud, "tipo_solicitud"),
        nullable=False,
        default=TipoSolicitud.OTRO,
        server_default=TipoSolicitud.OTRO.value,
    )
    direccion: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ubicacion: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    origen: Mapped[OrigenSolicitud] = mapped_column(
        pg_enum(OrigenSolicitud, "origen_solicitud"),
        nullable=False, default=OrigenSolicitud.MANUAL, server_default=OrigenSolicitud.MANUAL.value,
    )
    prioridad_ia: Mapped[PrioridadSolicitud] = mapped_column(
        pg_enum(PrioridadSolicitud, "prioridad_solicitud"),
        nullable=False, default=PrioridadSolicitud.PENDIENTE, server_default=PrioridadSolicitud.PENDIENTE.value,
    )
    prioridad_manual: Mapped[PrioridadSolicitud | None] = mapped_column(
        pg_enum(PrioridadSolicitud, "prioridad_solicitud"), nullable=True
    )
    # reemplazan al ENUM entidad_sugerida_ia — apuntan a una organización real
    organizacion_objetivo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )
    organizacion_manual_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )
    confianza_ia: Mapped[float | None] = mapped_column(Float, nullable=True)
    razonamiento_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    modificado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True
    )
    estado: Mapped[EstadoSolicitud] = mapped_column(
        pg_enum(EstadoSolicitud, "estado_solicitud"),
        nullable=False, default=EstadoSolicitud.PENDIENTE, server_default=EstadoSolicitud.PENDIENTE.value,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<SolicitudAyuda {self.id} {self.estado} {self.prioridad_ia}>"
