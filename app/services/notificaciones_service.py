"""Push a un grupo de usuarios: busca sus tokens, envía y borra los que FCM rechaza.

Lo usan los jobs de alertas, reportes y personas encontradas.
"""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations import firebase_client
from app.repositories import dispositivos_repository


def notificar_usuarios(
    db: Session, usuario_ids: Iterable[UUID], titulo: str, cuerpo: str, datos: dict[str, str] | None = None
) -> int:
    """Devuelve a cuántos dispositivos se intentó enviar."""
    tokens = dispositivos_repository.tokens_de_usuarios(db, usuario_ids)
    invalidos = firebase_client.enviar_push(tokens, titulo, cuerpo, datos)
    if invalidos:
        dispositivos_repository.eliminar_tokens(db, invalidos)
        db.commit()
    return len(tokens)
