"""Campañas y donaciones (B5). **La app no procesa pagos**: la organización registra lo que
recibe y publica campañas con lo que necesita.

Reglas de acceso:
- Campañas: cualquiera con sesión ve las vigentes (activas y sin vencer). El administrador ve
  y gestiona las de su organización; el super admin, todas.
- Donaciones: solo el administrador (su organización) y el super admin las registran y las ven.
- Una donación puede sumar a una campaña de la misma organización y venir a un centro.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import DatosInvalidos, NoEncontrado, SinPermiso
from app.middlewares.role_middleware import ROLES_ADMIN, alcance_organizacion, verificar_misma_organizacion
from app.models.campana import Campana
from app.models.centro_ayuda import CentroAyuda
from app.models.donacion import Donacion
from app.models.enums import EstadoDonacion, RolUsuario
from app.models.usuario import Usuario
from app.repositories import donaciones_repository as repo
from app.repositories import organizaciones_repository
from app.schemas.donaciones_schema import (
    CampanaCambiosIn,
    CampanaIn,
    CampanaOut,
    DonacionEstadoIn,
    DonacionIn,
)
from app.utils.paginacion import Paginacion


def _propia(usuario: Usuario, organizacion_id: UUID | None) -> bool:
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        return True
    return usuario.rol == RolUsuario.ADMINISTRADOR and organizacion_id is not None and organizacion_id == usuario.organizacion_id


def campanas_salida(db: Session, usuario: Usuario, campanas: list[Campana]) -> list[CampanaOut]:
    recaudado = repo.recaudado_por_campana(db, [c.id for c in campanas])
    return [
        CampanaOut.model_validate(c).model_copy(
            update={"recaudado": recaudado.get(c.id, 0.0), "propia": _propia(usuario, c.organizacion_id)}
        )
        for c in campanas
    ]


# --- campañas ---


def listar_campanas(db: Session, usuario: Usuario, *, todas: bool) -> list[Campana]:
    """`todas`: el administrador ve también las cerradas de su organización; el super admin, todas."""
    if todas and usuario.rol in ROLES_ADMIN:
        return repo.listar_campanas(db, solo_vigentes=False, organizacion_id=alcance_organizacion(usuario))
    return repo.listar_campanas(db, solo_vigentes=True, organizacion_id=None)


def _organizacion_destino(db: Session, usuario: Usuario, solicitada: UUID | None) -> UUID | None:
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        if solicitada is not None and organizaciones_repository.obtener_por_id(db, solicitada) is None:
            raise DatosInvalidos("La organización indicada no existe", codigo="ORGANIZACION_NO_ENCONTRADA")
        return solicitada
    if solicitada is not None and solicitada != usuario.organizacion_id:
        raise SinPermiso("Solo el super admin puede elegir otra organización", codigo="ORGANIZACION_NO_PERMITIDA")
    return usuario.organizacion_id


def crear_campana(db: Session, usuario: Usuario, datos: CampanaIn) -> Campana:
    campana = repo.crear_campana(
        db,
        **datos.model_dump(exclude={"organizacion_id"}),
        organizacion_id=_organizacion_destino(db, usuario, datos.organizacion_id),
        creado_por=usuario.id,
    )
    db.commit()
    return campana


def _campana_gestionable(db: Session, usuario: Usuario, campana_id: UUID) -> Campana:
    campana = repo.obtener_campana(db, campana_id)
    if campana is None:
        raise NoEncontrado("La campaña no existe", codigo="CAMPANA_NO_ENCONTRADA")
    verificar_misma_organizacion(usuario, campana.organizacion_id)
    return campana


def actualizar_campana(db: Session, usuario: Usuario, campana_id: UUID, cambios: CampanaCambiosIn) -> Campana:
    campana = repo.actualizar(db, _campana_gestionable(db, usuario, campana_id), **cambios.model_dump(exclude_unset=True))
    db.commit()
    return campana


# --- donaciones ---


def registrar_donacion(db: Session, usuario: Usuario, datos: DonacionIn) -> Donacion:
    organizacion_id = usuario.organizacion_id
    if datos.campana_id is not None:
        campana = _campana_gestionable(db, usuario, datos.campana_id)
        organizacion_id = campana.organizacion_id
        if campana.categoria != datos.categoria:
            raise DatosInvalidos(
                f"La campaña recibe {campana.categoria}, no {datos.categoria}", codigo="CATEGORIA_DISTINTA"
            )
    if datos.centro_id is not None and db.get(CentroAyuda, datos.centro_id) is None:
        raise NoEncontrado("El centro no existe", codigo="CENTRO_NO_ENCONTRADO")
    donacion = repo.crear_donacion(
        db, **datos.model_dump(), organizacion_id=organizacion_id, registrada_por=usuario.id
    )
    db.commit()
    return donacion


def listar_donaciones(
    db: Session,
    usuario: Usuario,
    pag: Paginacion,
    *,
    categoria: str | None,
    estado: EstadoDonacion | None,
    campana_id: UUID | None,
) -> tuple[list[Donacion], int]:
    return repo.listar_donaciones(
        db,
        pag,
        organizacion_id=alcance_organizacion(usuario),
        categoria=categoria,
        estado=estado,
        campana_id=campana_id,
    )


def cambiar_estado(db: Session, usuario: Usuario, donacion_id: UUID, datos: DonacionEstadoIn) -> Donacion:
    donacion = repo.obtener_donacion(db, donacion_id)
    if donacion is None:
        raise NoEncontrado("La donación no existe", codigo="DONACION_NO_ENCONTRADA")
    verificar_misma_organizacion(usuario, donacion.organizacion_id)
    donacion = repo.actualizar(db, donacion, estado=datos.estado)
    db.commit()
    return donacion
