import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContactoEmergencia(Base):
    __tablename__ = "contactos_emergencia"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Índice y borrado en cascada: migración 0014
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    # Formato E.164: +573001234567 (lo exige Twilio para el SMS del SOS)
    telefono: Mapped[str] = mapped_column(String(15), nullable=False)
    parentesco: Mapped[str | None] = mapped_column(String(15), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<ContactoEmergencia {self.id} {self.nombre}>"
