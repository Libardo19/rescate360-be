import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import MetodoEnvio, pg_enum


class ColaAlertaOffline(Base):
    __tablename__ = "cola_alertas_offline"
    __table_args__ = (
        # Creados en la migración 0003
        Index("ix_cola_alertas_offline_ubicacion", "ubicacion", postgresql_using="gist"),
        # Migración 0020
        Index("ix_cola_alertas_offline_sincronizado", "sincronizado"),
        CheckConstraint("saltos BETWEEN 0 AND 8", name="chk_cola_alertas_offline_saltos"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    uuid_origen: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ubicacion: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    metodo_envio: Mapped[MetodoEnvio] = mapped_column(pg_enum(MetodoEnvio, "metodo_envio"), nullable=False)
    generado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sincronizado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Relevo (migración 0020): quién lo subió (puede no ser el autor), cuántos saltos dio y qué se hizo
    subido_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    saltos: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0, server_default="0")
    resultado: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recibido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<ColaAlertaOffline {self.id} sync={self.sincronizado}>"
