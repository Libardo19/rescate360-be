import uuid

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, String, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CentroAyuda(Base):
    __tablename__ = 'centros_ayuda'
    __table_args__ = (
        Index('ix_centros_ayuda_organizacion_id', 'organizacion_id'),
        Index('ix_centros_ayuda_ubicacion', 'ubicacion', postgresql_using='gist'),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()')
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("activo"))
    direccion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ubicacion: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False
    )
    recursos_disponibles: Mapped[str | None] = mapped_column(Text, nullable=True)
    gestionado_por: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('usuarios.id'), nullable=False)
    organizacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey('organizaciones.id'), nullable=True
    )

    def __repr__(self) -> str:
        return f'<CentroAyuda {self.id} {self.nombre}>'
