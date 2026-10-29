import uuid
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EstadoCasoPersona, pg_enum


class PersonaDesaparecida(Base):
    __tablename__ = "personas_desaparecidas"
    __table_args__ = (
        # Creados en la migración 0003
        Index("ix_personas_desaparecidas_ultima_ubicacion", "ultima_ubicacion", postgresql_using="gist"),
        # Migración 0013
        Index("ix_personas_desaparecidas_estado_caso", "estado_caso"),
        Index("ix_personas_desaparecidas_reportado_por", "reportado_por"),
        CheckConstraint("edad BETWEEN 0 AND 120", name="chk_personas_desaparecidas_edad"),
        CheckConstraint("sexo IN ('femenino', 'masculino', 'otro')", name="chk_personas_desaparecidas_sexo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reportado_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    # Ruta dentro del storage ("personas/<uuid>.jpg"); la URL pública la arma storage_client
    foto_ruta: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ultima_ubicacion: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )
    estado_caso: Mapped[EstadoCasoPersona] = mapped_column(
        pg_enum(EstadoCasoPersona, "estado_caso_persona"),
        nullable=False, default=EstadoCasoPersona.BUSCANDO, server_default=EstadoCasoPersona.BUSCANDO.value,
    )

    # Ficha (migración 0013). Nullable solo por las filas viejas: la API los exige.
    edad: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    sexo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    estatura: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fecha_vista: Mapped[date | None] = mapped_column(Date, nullable=True)
    lugar: Mapped[str | None] = mapped_column(String(100), nullable=True)
    senas_particulares: Mapped[str | None] = mapped_column(Text, nullable=True)
    vestimenta: Mapped[str | None] = mapped_column(Text, nullable=True)
    contacto_nombre: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # E.164, como todos los teléfonos del sistema
    contacto_telefono: Mapped[str | None] = mapped_column(String(15), nullable=True)
    # Ley 1098/2006: la foto de un menor solo la ven quien reportó y los administradores
    es_menor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    encontrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    autor: Mapped["Usuario"] = relationship(foreign_keys=[reportado_por], lazy="selectin")

    def __repr__(self) -> str:
        return f"<PersonaDesaparecida {self.id} {self.nombre} {self.estado_caso}>"
