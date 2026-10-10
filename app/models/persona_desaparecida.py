import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoCasoPersona, pg_enum


class PersonaDesaparecida(Base):
    __tablename__ = "personas_desaparecidas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reportado_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    caracteristicas: Mapped[str] = mapped_column(Text, nullable=False)
    foto_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ultima_ubicacion: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False
    )
    estado_caso: Mapped[EstadoCasoPersona] = mapped_column(
        pg_enum(EstadoCasoPersona, "estado_caso_persona"),
        nullable=False, default=EstadoCasoPersona.BUSCANDO, server_default=EstadoCasoPersona.BUSCANDO.value,
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<PersonaDesaparecida {self.id} {self.nombre} {self.estado_caso}>"
