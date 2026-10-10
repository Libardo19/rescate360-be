import uuid

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContactoEmergencia(Base):
    __tablename__ = "contactos_emergencia"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    telefono: Mapped[str] = mapped_column(String(10), nullable=False)
    parentesco: Mapped[str | None] = mapped_column(String(15), nullable=True)

    def __repr__(self) -> str:
        return f"<ContactoEmergencia {self.id} {self.nombre}>"
