from datetime import UTC, datetime
from uuid import UUID

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import EstadoUsuario, RolUsuario
from app.models.usuario import Usuario
from app.utils.paginacion import Paginacion


def obtener_por_id(db: Session, usuario_id: UUID) -> Usuario | None:
    return db.get(Usuario, usuario_id)


def obtener_por_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(func.lower(Usuario.email) == email.lower()))


def crear(db: Session, **campos) -> Usuario:
    usuario = Usuario(**campos)
    db.add(usuario)
    db.flush()  # asigna el id generado por la BD
    return usuario


def registrar_acceso(db: Session, usuario: Usuario) -> None:
    usuario.ultimo_acceso = datetime.now(UTC)
    db.flush()


def actualizar_ubicacion(db: Session, usuario: Usuario, ubicacion: WKTElement) -> Usuario:
    usuario.ubicacion_actual = ubicacion
    usuario.ubicacion_actualizada_en = datetime.now(UTC)
    db.flush()
    db.refresh(usuario)  # ubicacion_actual vuelve como WKBElement, igual que al leerla
    return usuario


def borrar_ubicacion(db: Session, usuario: Usuario) -> None:
    usuario.ubicacion_actual = None
    usuario.ubicacion_actualizada_en = None
    db.flush()


def listar(
    db: Session,
    pag: Paginacion,
    *,
    organizacion_id: UUID | None = None,
    rol: RolUsuario | None = None,
    estado: EstadoUsuario | None = None,
    q: str | None = None,
) -> tuple[list[Usuario], int]:
    filtros = []
    if organizacion_id is not None:
        filtros.append(Usuario.organizacion_id == organizacion_id)
    if rol is not None:
        filtros.append(Usuario.rol == rol)
    if estado is not None:
        filtros.append(Usuario.estado == estado)
    if q:
        patron = f"%{q}%"
        filtros.append(or_(Usuario.nombre.ilike(patron), Usuario.email.ilike(patron), Usuario.codigo.ilike(patron)))

    total = db.scalar(select(func.count()).select_from(Usuario).where(*filtros)) or 0
    consulta = (
        select(Usuario)
        .where(*filtros)
        .order_by(Usuario.creado_en.desc(), Usuario.id)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total


def actualizar(db: Session, usuario: Usuario, **campos) -> Usuario:
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)
    db.flush()
    db.refresh(usuario)
    return usuario


def contar_super_admins_activos(db: Session) -> int:
    """Cuenta los super admins activos BLOQUEANDO sus filas (FOR UPDATE).

    Si dos super admins se bloquean entre sí al mismo tiempo, el segundo espera al primero
    y ve el conteo ya actualizado: el sistema nunca queda sin un super admin activo.
    """
    consulta = (
        select(Usuario.id)
        .where(Usuario.rol == RolUsuario.SUPER_ADMIN, Usuario.estado == EstadoUsuario.ACTIVO)
        .with_for_update()
    )
    return len(db.scalars(consulta).all())
