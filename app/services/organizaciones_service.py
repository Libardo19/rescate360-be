"""Organizaciones y sus administradores.

- Crear, editar y activar/desactivar organizaciones: solo super admin.
- Voluntarios y administradores solo ven la suya; el super admin, todas.
- Desactivar una organización deja sin acceso a su gente (lo revisa `verificar_estado`).
- Los administradores se crean por invitación (mismo flujo que los voluntarios) y
  "revocar" es bloquearlos: el rol no se puede quitar porque el CHECK de la BD ata
  administrador ↔ organización, y bloquear se puede deshacer.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import Conflicto, DatosInvalidos, NoEncontrado
from app.middlewares.role_middleware import es_super_admin, verificar_misma_organizacion
from app.models.enums import EstadoUsuario, RolUsuario, TipoOrganizacion
from app.models.organizacion import Organizacion
from app.models.usuario import Usuario
from app.repositories import organizaciones_repository as repo
from app.repositories import usuarios_repository
from app.schemas.organizaciones_schema import OrganizacionCambiosIn, OrganizacionIn
from app.schemas.usuarios_schema import InvitacionOut, UsuarioNuevoIn
from app.services import usuarios_service
from app.utils.paginacion import Paginacion


def listar(
    db: Session,
    actor: Usuario,
    pag: Paginacion,
    *,
    tipo: TipoOrganizacion | None,
    activa: bool | None,
    q: str | None,
) -> tuple[list[Organizacion], int]:
    solo_id = None if es_super_admin(actor) else actor.organizacion_id
    return repo.listar(db, pag, solo_id=solo_id, tipo=tipo, activa=activa, q=q)


def obtener(db: Session, actor: Usuario, organizacion_id: UUID) -> Organizacion:
    organizacion = repo.obtener_por_id(db, organizacion_id)
    if organizacion is None:
        raise NoEncontrado("La organización no existe", codigo="ORGANIZACION_NO_ENCONTRADA")
    verificar_misma_organizacion(actor, organizacion.id)
    return organizacion


def crear(db: Session, datos: OrganizacionIn) -> Organizacion:
    organizacion = repo.crear(db, **datos.model_dump())
    db.commit()
    return organizacion


def actualizar(db: Session, actor: Usuario, organizacion_id: UUID, cambios: OrganizacionCambiosIn) -> Organizacion:
    organizacion = obtener(db, actor, organizacion_id)
    campos = cambios.model_dump(exclude_unset=True)
    for obligatorio in ("nombre", "tipo", "activa"):
        if obligatorio in campos and campos[obligatorio] is None:
            raise DatosInvalidos(f"El campo {obligatorio} no puede quedar vacío", codigo="DATOS_INVALIDOS")
    organizacion = repo.actualizar(db, organizacion, **campos)
    db.commit()
    return organizacion


# --- Administradores de una organización (solo super admin) ---


def crear_administrador(db: Session, actor: Usuario, organizacion_id: UUID, datos: UsuarioNuevoIn) -> InvitacionOut:
    organizacion = obtener(db, actor, organizacion_id)
    if datos.organizacion_id is not None and datos.organizacion_id != organizacion.id:
        raise DatosInvalidos("La organización del cuerpo no coincide con la de la ruta", codigo="ORGANIZACION_NO_COINCIDE")
    if not organizacion.activa:
        raise Conflicto("La organización está desactivada", codigo="ORGANIZACION_INACTIVA")
    return usuarios_service.crear_invitado(
        db, datos=datos, rol=RolUsuario.ADMINISTRADOR, organizacion_id=organizacion.id
    )


def listar_administradores(
    db: Session, actor: Usuario, organizacion_id: UUID, pag: Paginacion
) -> tuple[list[Usuario], int]:
    organizacion = obtener(db, actor, organizacion_id)
    return usuarios_repository.listar(db, pag, organizacion_id=organizacion.id, rol=RolUsuario.ADMINISTRADOR)


def revocar_administrador(db: Session, actor: Usuario, organizacion_id: UUID, usuario_id: UUID) -> Usuario:
    organizacion = obtener(db, actor, organizacion_id)
    usuario = usuarios_repository.obtener_por_id(db, usuario_id)
    if usuario is None or usuario.rol != RolUsuario.ADMINISTRADOR or usuario.organizacion_id != organizacion.id:
        raise NoEncontrado("Ese administrador no pertenece a la organización", codigo="ADMINISTRADOR_NO_ENCONTRADO")
    usuario = usuarios_repository.actualizar(db, usuario, estado=EstadoUsuario.BLOQUEADO)
    db.commit()
    return usuario
