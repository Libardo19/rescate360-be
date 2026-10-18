"""Permisos por rol y alcance de los datos (sección 4 de docs/PLAN_BACKEND.md).

Restringir un endpoint a ciertos roles:

    from app.middlewares.role_middleware import require_role

    @router.patch("/{id}/verificar")
    def verificar(id: UUID, usuario: Usuario = Depends(require_role(RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN))): ...

Acotar una consulta en el service o repository:

    org_id = alcance_organizacion(usuario)   # None = sin filtro (solo super_admin)
    if org_id is not None:
        consulta = consulta.where(Reporte.organizacion_objetivo_id == org_id)

    dueno_id = solo_propio(usuario)          # el ciudadano solo ve lo suyo
    if dueno_id is not None:
        consulta = consulta.where(Reporte.usuario_id == dueno_id)
"""

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends

from app.core.excepciones import SinPermiso
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import RolUsuario
from app.models.usuario import Usuario

ROLES_ADMIN = (RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN)
ROLES_OPERATIVOS = (RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN)


def require_role(*roles: RolUsuario) -> Callable[..., Usuario]:
    """Dependencia que deja pasar solo a los roles indicados y devuelve el usuario."""
    permitidos = frozenset(roles)

    def dependencia(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in permitidos:
            raise SinPermiso("No tienes permiso para esta acción")
        return usuario

    return dependencia


def es_super_admin(usuario: Usuario) -> bool:
    return usuario.rol == RolUsuario.SUPER_ADMIN


def alcance_organizacion(usuario: Usuario) -> UUID | None:
    """Organización a la que se acota la consulta.

    - super_admin → None (ve todo)
    - administrador y voluntario → su organizacion_id
    - ciudadano → SinPermiso: no tiene alcance de organización. Para él se usa solo_propio().
    """
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        return None
    if usuario.rol == RolUsuario.CIUDADANO:
        raise SinPermiso("No tienes permiso para esta acción")
    return usuario.organizacion_id


def solo_propio(usuario: Usuario) -> UUID | None:
    """El ciudadano solo ve lo que él creó: devuelve su id. Para los demás roles, None."""
    return usuario.id if usuario.rol == RolUsuario.CIUDADANO else None


def verificar_misma_organizacion(usuario: Usuario, organizacion_id: UUID | None) -> None:
    """Para acciones sobre un registro concreto: el admin o voluntario solo actúa en su organización."""
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        return
    if usuario.organizacion_id is None or usuario.organizacion_id != organizacion_id:
        raise SinPermiso("El registro pertenece a otra organización", codigo="FUERA_DE_ALCANCE")
