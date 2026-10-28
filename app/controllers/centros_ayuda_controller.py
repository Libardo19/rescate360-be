"""Controlador de centros de ayuda."""

from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user, get_current_user_optional
from app.middlewares.role_middleware import require_role
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.centros_ayuda_schema import CentroAyudaIn, CentroAyudaOut, CentroAyudaUpdate
from app.services import centros_ayuda_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def listar_centros(
    tipo: str | None = None,
    q: str | None = None,
    estado: str | None = None,
    solo_mis_centros: bool = False,
    ver_tambien_otros: bool = False,
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radio_m: float | None = Query(default=None, ge=0),
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> Pagina[CentroAyudaOut]:
    items, total = centros_ayuda_service.listar(
        db,
        usuario=usuario,
        tipo=tipo,
        q=q,
        estado=estado,
        solo_mis_centros=solo_mis_centros,
        ver_tambien_otros=ver_tambien_otros,
        lat=lat,
        lng=lng,
        radio_m=radio_m,
        pag=pag,
    )
    return Pagina.crear(items, total, pag)


def obtener_centro(
    centro_id: UUID,
    usuario: Usuario | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> CentroAyudaOut:
    return centros_ayuda_service.obtener(db, centro_id, usuario)


def crear_centro(
    datos: CentroAyudaIn,
    usuario: Usuario = Depends(require_role(RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> CentroAyudaOut:
    return centros_ayuda_service.crear(db, usuario, datos)


def actualizar_centro(
    centro_id: UUID,
    datos: CentroAyudaUpdate,
    usuario: Usuario = Depends(require_role(RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN)),
    db: Session = Depends(get_db),
) -> CentroAyudaOut:
    return centros_ayuda_service.actualizar(db, usuario, centro_id, datos)
