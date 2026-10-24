import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Donacion(Base):
    __tablename__ = "donaciones"
    __table_args__ = (
        Index("ix_donaciones_organizacion_id", "organizacion_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    centro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_ayuda.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(25), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    unidad: Mapped[str] = mapped_column(String(20), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    organizacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Donacion {self.id} {self.tipo} {self.cantidad}{self.unidad}>"
