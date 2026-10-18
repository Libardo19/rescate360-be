"""Dispositivos del usuario para notificaciones push (FCM).

Una persona puede tener varios teléfonos, o cambiar de teléfono: por eso es una
tabla y no una columna de `usuarios`. El token es único: si otro usuario inicia
sesión en el mismo teléfono, el token pasa a ese usuario.

Lo escribe el módulo `usuarios` (Dev A, `POST /usuarios/me/dispositivo`) y lo lee
el envío de push (Dev B, `firebase_client` y `notificar_alerta_zona`).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import PlataformaDispositivo, pg_enum


class Dispositivo(Base):
    __tablename__ = "dispositivos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_push: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    plataforma: Mapped[PlataformaDispositivo] = mapped_column(
        pg_enum(PlataformaDispositivo, "plataforma_dispositivo"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Dispositivo {self.usuario_id} {self.plataforma}>"
