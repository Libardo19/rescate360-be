from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auditoria import Auditoria
from app.models.enums import OperacionAuditoria
from app.models.usuario import Usuario
from app.utils.paginacion import Paginacion


def listar(
    db: Session,
    pag: Paginacion,
    *,
    organizacion_id: UUID | None = None,
    tabla: str | None = None,
    registro_id: UUID | None = None,
    usuario_id: UUID | None = None,
    operacion: OperacionAuditoria | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> tuple[list[tuple[Auditoria, Usuario | None]], int]:
    """Filas con su actor. `organizacion_id` = solo lo que hicieron los usuarios de esa organización."""
    filtros = []
    if organizacion_id is not None:
        miembros = select(Usuario.id).where(Usuario.organizacion_id == organizacion_id)
        filtros.append(Auditoria.usuario_id.in_(miembros))
    if tabla is not None:
        filtros.append(Auditoria.tabla == tabla)
    if registro_id is not None:
        filtros.append(Auditoria.registro_id == registro_id)
    if usuario_id is not None:
        filtros.append(Auditoria.usuario_id == usuario_id)
    if operacion is not None:
        filtros.append(Auditoria.operacion == operacion)
    if desde is not None:
        filtros.append(Auditoria.creado_en >= desde)
    if hasta is not None:
        filtros.append(Auditoria.creado_en <= hasta)

    total = db.scalar(select(func.count()).select_from(Auditoria).where(*filtros)) or 0
    consulta = (
        select(Auditoria, Usuario)
        .outerjoin(Usuario, Usuario.id == Auditoria.usuario_id)
        .where(*filtros)
        .order_by(Auditoria.creado_en.desc(), Auditoria.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return [(fila, actor) for fila, actor in db.execute(consulta).all()], total
