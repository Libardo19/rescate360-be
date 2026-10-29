import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.campana import CATEGORIAS_SQL
from app.models.enums import EstadoDonacion, pg_enum


class Donacion(Base):
    """Donación registrada por la organización (migración 0021). La app no procesa pagos."""

    __tablename__ = "donaciones"
    __table_args__ = (
        Index("ix_donaciones_organizacion_id", "organizacion_id"),
        Index("ix_donaciones_campana_id", "campana_id"),
        CheckConstraint(f"categoria IN {CATEGORIAS_SQL}", name="chk_donaciones_categoria"),
        CheckConstraint("cantidad > 0", name="chk_donaciones_cantidad"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Centro que la recibe (opcional) y campaña a la que suma (opcional)
    centro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_ayuda.id"), nullable=True)
    campana_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("campanas.id"), nullable=True)
    categoria: Mapped[str] = mapped_column(String(15), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    unidad: Mapped[str] = mapped_column(String(20), nullable=False)
    # Solo para dinero (en pesos)
    monto: Mapped[float | None] = mapped_column(Float, nullable=True)
    estado: Mapped[EstadoDonacion] = mapped_column(
        pg_enum(EstadoDonacion, "estado_donacion"),
        nullable=False, default=EstadoDonacion.RECIBIDA, server_default=EstadoDonacion.RECIBIDA.value,
    )
    registrada_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    organizacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Donacion {self.id} {self.categoria} {self.cantidad}{self.unidad}>"
