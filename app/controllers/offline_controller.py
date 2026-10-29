"""HTTP del modo sin conexión: arma la respuesta y llama al service. Sin SQL ni reglas."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.usuario import Usuario
from app.schemas.offline_schema import LlaveOfflineOut, LoteOfflineIn, LoteOfflineOut
from app.services import offline_service


def obtener_llave(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> LlaveOfflineOut:
    return LlaveOfflineOut(llave=offline_service.llave(db, usuario))


def sincronizar(
    lote: LoteOfflineIn, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> LoteOfflineOut:
    return offline_service.recibir(db, usuario, lote, relevo=False)


def relevar(
    lote: LoteOfflineIn, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> LoteOfflineOut:
    return offline_service.recibir(db, usuario, lote, relevo=True)
