import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoZona, pg_enum


class ZonaPeligrosa(Base):
    __tablename__ = "zonas_peligrosas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tipo_riesgo: Mapped[str] = mapped_column(String(30), nullable=False)
    area: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False), nullable=False
    )
    estado: Mapped[EstadoZona] = mapped_column(
        pg_enum(EstadoZona, "estado_zona"),
        nullable=False, default=EstadoZona.ACTIVA, server_default=EstadoZona.ACTIVA.value,
    )
    gestionado_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<ZonaPeligrosa {self.id} {self.tipo_riesgo} {self.estado}>"
