"""HTTP de auditoría: arma la respuesta y llama al service. Sin SQL ni reglas."""

from datetime import datetime
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import OperacionAuditoria
from app.models.usuario import Usuario
from app.schemas.auditoria_schema import AuditoriaOut
from app.services import auditoria_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def listar_auditoria(
    tabla: str | None = None,
    registro_id: UUID | None = None,
    usuario_id: UUID | None = None,
    operacion: OperacionAuditoria | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[AuditoriaOut]:
    items, total = auditoria_service.listar(
        db, usuario, pag, tabla=tabla, registro_id=registro_id, usuario_id=usuario_id,
        operacion=operacion, desde=desde, hasta=hasta,
    )
    return Pagina.crear(items, total, pag)
