"""Autorizaciones que da el usuario (Ley 1581 de 2012, Decreto 1074 de 2015).

Es la evidencia legal de que el titular autorizó el tratamiento de sus datos:
qué autorizó, qué versión de la política aceptó, cuándo y desde qué IP.
Nunca se borra; si el usuario retira la autorización se registra otra fila con
`aceptado = false`.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import TipoConsentimiento, pg_enum


class Consentimiento(Base):
    __tablename__ = "consentimientos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True
    )
    tipo: Mapped[TipoConsentimiento] = mapped_column(
        pg_enum(TipoConsentimiento, "tipo_consentimiento"), nullable=False
    )
    aceptado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version_politica: Mapped[str] = mapped_column(String(20), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Consentimiento {self.usuario_id} {self.tipo} aceptado={self.aceptado}>"
