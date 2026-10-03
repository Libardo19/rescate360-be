
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import RolUsuario, pg_enum


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint(
            "(rol IN ('voluntario','administrador') AND organizacion_id IS NOT NULL) "
            "OR (rol IN ('ciudadano','super_admin') AND organizacion_id IS NULL)",
            name="chk_organizacion_segun_rol",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(10), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    rol: Mapped[RolUsuario] = mapped_column(
        pg_enum(RolUsuario, "rol_usuario"),
        nullable=False, default=RolUsuario.CIUDADANO, server_default=RolUsuario.CIUDADANO.value,
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organizacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizaciones.id"), nullable=True
    )
    organizacion: Mapped["Organizacion | None"] = relationship(back_populates="usuarios")

    ubicacion_actual: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
    )

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Usuario {self.id} {self.email} {self.rol}>"
