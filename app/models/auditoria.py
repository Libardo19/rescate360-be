"""Alimentada por el trigger fn_auditoria() de Postgres""" 

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import OperacionAuditoria, pg_enum


class Auditoria(Base):
    __tablename__ = "auditoria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tabla: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    registro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    operacion: Mapped[OperacionAuditoria] = mapped_column(
        pg_enum(OperacionAuditoria, "operacion_auditoria"), nullable=False
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True, index=True
    )
    datos_anteriores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    datos_nuevos: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    campos_modificados: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Auditoria {self.tabla}:{self.registro_id} {self.operacion}>"
