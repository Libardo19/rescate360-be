import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvidenciaReporte(Base):
    """Foto o video de un reporte (migración 0010). El archivo vive en el almacenamiento;
    aquí solo queda su ruta relativa."""

    __tablename__ = "evidencias_reporte"
    __table_args__ = (
        CheckConstraint("tipo IN ('foto', 'video')", name="chk_evidencias_reporte_tipo"),
        Index("ix_evidencias_reporte_reporte_id", "reporte_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reporte_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reportes.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)  # foto | video
    ruta: Mapped[str] = mapped_column(String(500), nullable=False)
    mime: Mapped[str] = mapped_column(String(50), nullable=False)
    tamano_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<EvidenciaReporte {self.id} {self.tipo}>"
