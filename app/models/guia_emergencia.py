import uuid

from sqlalchemy import String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GuiaEmergencia(Base):
    __tablename__ = "guia_emergencia"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    titulo: Mapped[str] = mapped_column(String(50), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(String(25), nullable=False)

    def __repr__(self) -> str:
        return f"<GuiaEmergencia {self.id} {self.titulo}>"
