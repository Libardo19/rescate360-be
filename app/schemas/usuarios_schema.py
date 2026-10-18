from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import EstadoUsuario, RolUsuario


class UsuarioOut(BaseModel):
    """Usuario tal como lo ven los front (nunca incluye password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    email: str
    telefono: str | None
    rol: RolUsuario
    estado: EstadoUsuario
    organizacion_id: UUID | None
    ultimo_acceso: datetime | None
    creado_en: datetime
