"""HTTP de organizaciones: arma la respuesta y llama al service. Sin SQL ni reglas."""

from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import TipoOrganizacion
from app.models.usuario import Usuario
from app.schemas.organizaciones_schema import OrganizacionCambiosIn, OrganizacionIn, OrganizacionOut
from app.schemas.usuarios_schema import InvitacionOut, UsuarioNuevoIn, UsuarioOut
from app.services import organizaciones_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def listar(
    tipo: TipoOrganizacion | None = None,
    activa: bool | None = None,
    q: str | None = None,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[OrganizacionOut]:
    items, total = organizaciones_service.listar(db, usuario, pag, tipo=tipo, activa=activa, q=q)
    return Pagina.crear([OrganizacionOut.model_validate(o) for o in items], total, pag)


def obtener(
    organizacion_id: UUID,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizacionOut:
    return OrganizacionOut.model_validate(organizaciones_service.obtener(db, usuario, organizacion_id))


def crear(datos: OrganizacionIn, db: Session = Depends(get_db)) -> OrganizacionOut:
    return OrganizacionOut.model_validate(organizaciones_service.crear(db, datos))


def actualizar(
    organizacion_id: UUID,
    datos: OrganizacionCambiosIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizacionOut:
    return OrganizacionOut.model_validate(organizaciones_service.actualizar(db, usuario, organizacion_id, datos))


def listar_administradores(
    organizacion_id: UUID,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[UsuarioOut]:
    items, total = organizaciones_service.listar_administradores(db, usuario, organizacion_id, pag)
    return Pagina.crear([UsuarioOut.model_validate(u) for u in items], total, pag)


def crear_administrador(
    organizacion_id: UUID,
    datos: UsuarioNuevoIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvitacionOut:
    return organizaciones_service.crear_administrador(db, usuario, organizacion_id, datos)


def revocar_administrador(
    organizacion_id: UUID,
    usuario_id: UUID,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    revocado = organizaciones_service.revocar_administrador(db, usuario, organizacion_id, usuario_id)
    return UsuarioOut.model_validate(revocado)
