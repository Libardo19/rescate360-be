"""Mensajes del modo sin conexión (B7 ampliado).

El teléfono arma un mensaje pequeño (menos de 512 bytes) y lo firma con su `llave_offline`:

    firma = HMAC-SHA256(llave, "uuid_origen|usuario_id|tipo|lat|lng|generado_en") en hex
    (lat y lng con 6 decimales; generado_en tal como lo mandó el teléfono, en ISO 8601)

`saltos` no entra en la firma: cada teléfono que lo pasa le suma uno.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TipoMensaje = Literal["sos", "necesito_ayuda", "a_salvo", "sin_respuesta"]
MAXIMO_SALTOS = 8
MAXIMO_POR_LOTE = 50


def texto_a_firmar(uuid_origen: UUID, usuario_id: UUID, tipo: str, lat: float, lng: float, generado_en: str) -> str:
    return f"{uuid_origen}|{usuario_id}|{tipo}|{lat:.6f}|{lng:.6f}|{generado_en}"


class MensajeOffline(BaseModel):
    uuid_origen: UUID
    usuario_id: UUID
    tipo: TipoMensaje
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    # Texto exacto que firmó el teléfono (por eso no se parsea aquí)
    generado_en: str = Field(min_length=10, max_length=40)
    saltos: int = Field(default=0, ge=0)
    firma: str = Field(min_length=64, max_length=64)

    def generado(self) -> datetime:
        return datetime.fromisoformat(self.generado_en.replace("Z", "+00:00"))


class LoteOfflineIn(BaseModel):
    mensajes: list[MensajeOffline] = Field(min_length=1, max_length=MAXIMO_POR_LOTE)


class RechazoOut(BaseModel):
    uuid_origen: UUID
    motivo: str  # FIRMA_INVALIDA, MENSAJE_VENCIDO, DEMASIADOS_SALTOS, USUARIO_DESCONOCIDO, NO_ES_TUYO…


class LoteOfflineOut(BaseModel):
    aceptados: int
    duplicados: int
    rechazados: list[RechazoOut]


class LlaveOfflineOut(BaseModel):
    llave: str
