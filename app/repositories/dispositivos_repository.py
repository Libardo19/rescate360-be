"""Tokens push de los dispositivos.

Lo escribe el módulo `usuarios` (Dev A) y lo lee el envío de push (Dev B):

    tokens = dispositivos_repository.tokens_de_usuarios(db, usuario_ids)
"""

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.dispositivo import Dispositivo
from app.models.enums import PlataformaDispositivo


def registrar(db: Session, *, usuario_id: UUID, token_push: str, plataforma: PlataformaDispositivo) -> Dispositivo:
    """Inserta el token o, si ya existe, se lo pasa a este usuario (otro inició sesión en el mismo teléfono).

    Un solo INSERT ... ON CONFLICT: dos registros simultáneos del mismo token no chocan.
    """
    consulta = (
        insert(Dispositivo)
        .values(usuario_id=usuario_id, token_push=token_push, plataforma=plataforma)
        .on_conflict_do_update(
            index_elements=[Dispositivo.token_push],
            set_={"usuario_id": usuario_id, "plataforma": plataforma, "actualizado_en": func.now()},
        )
        .returning(Dispositivo)
    )
    dispositivo = db.scalars(consulta, execution_options={"populate_existing": True}).one()
    db.flush()
    return dispositivo


def eliminar(db: Session, *, usuario_id: UUID, token_push: str) -> int:
    """Borra el token solo si es de este usuario. Devuelve cuántas filas borró (0 o 1)."""
    consulta = delete(Dispositivo).where(Dispositivo.usuario_id == usuario_id, Dispositivo.token_push == token_push)
    return db.execute(consulta).rowcount


def tokens_de_usuarios(db: Session, usuario_ids: Iterable[UUID]) -> list[str]:
    """Tokens de todos los dispositivos de esos usuarios (para el envío de push en lote)."""
    ids = list(usuario_ids)
    if not ids:
        return []
    return list(db.scalars(select(Dispositivo.token_push).where(Dispositivo.usuario_id.in_(ids))))


def eliminar_tokens(db: Session, tokens: Iterable[str]) -> int:
    """Borra tokens que FCM marcó como inválidos (la app se desinstaló o el token venció)."""
    lista = list(tokens)
    if not lista:
        return 0
    return db.execute(delete(Dispositivo).where(Dispositivo.token_push.in_(lista))).rowcount
