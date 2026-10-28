"""Servicio de centros de ayuda."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import Conflicto, DatosInvalidos, NoEncontrado, SinPermiso
from app.middlewares.auth_middleware import get_current_user
from app.middlewares.role_middleware import es_super_admin
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.repositories import centros_ayuda_repository as repo
from app.schemas.centros_ayuda_schema import CentroAyudaIn, CentroAyudaOut, CentroAyudaUpdate
from app.utils.geo import punto_desde_latlng
from app.utils.paginacion import Paginacion


def _puede_crear_o_modificar(usuario: Usuario) -> bool:
    return usuario.rol in (RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN)


def _puede_modificar_centro(usuario: Usuario, centro) -> bool:
    if es_super_admin(usuario):
        return True
    if usuario.rol == RolUsuario.ADMINISTRADOR:
        if usuario.organizacion_id is None or centro.organizacion_id is None:
            return False
        return usuario.organizacion_id == centro.organizacion_id
    if usuario.rol == RolUsuario.VOLUNTARIO:
        return False
    return False


def _puede_ver(usuario: Usuario | None) -> bool:
    # ciudadano y autenticados pueden ver
    return True


def listar(
    db: Session,
    *,
    usuario: Usuario | None = None,
    tipo: str | None = None,
    q: str | None = None,
    estado: str | None = None,
    solo_mis_centros: bool = False,
    ver_tambien_otros: bool = False,
    lat: float | None = None,
    lng: float | None = None,
    radio_m: float | None = None,
    pag: Paginacion | None = None,
) -> tuple[list[CentroAyudaOut], int]:
    incluir_solo_activos = True
    if usuario is not None:
        # admin, super admin y voluntario pueden ver según reglas; por defecto mostramos todo para permitir ver otros si lo piden
        incluir_solo_activos = False

    org_id = None
    if usuario is not None and usuario.rol in (RolUsuario.ADMINISTRADOR, RolUsuario.VOLUNTARIO):
        org_id = usuario.organizacion_id
    elif usuario is not None and usuario.rol == RolUsuario.SUPER_ADMIN:
        org_id = None

    # Si es admin o voluntario y solicita explícitamente solo sus centros, filtramos por su org
    # Si solicita ver también otros, no filtramos exclusivamente por su org
    usar_solo_mis = bool(solo_mis_centros and not ver_tambien_otros and org_id is not None)

    filas, total = repo.listar(
        db,
        pag,
        tipo=tipo,
        q=q,
        estado=estado,
        organizacion_id=org_id,
        incluir_solo_activos=incluir_solo_activos and usuario is None and estado is None,
        solo_mis_centros=usar_solo_mis,
        ver_tambien_otros=ver_tambien_otros,
        lat=lat,
        lng=lng,
        radio_m=radio_m,
    )
    items = [CentroAyudaOut.desde_modelo(centro, distancia_m=dist) for centro, dist in filas]
    return items, total


def obtener(db: Session, centro_id: UUID, usuario: Usuario | None = None) -> CentroAyudaOut:
    centro = repo.obtener_por_id(db, centro_id)
    if centro is None:
        raise NoEncontrado("Centro de ayuda no encontrado", codigo="CENTRO_NO_ENCONTRADO")
    return CentroAyudaOut.desde_modelo(centro)


def crear(db: Session, usuario: Usuario, datos: CentroAyudaIn) -> CentroAyudaOut:
    if not _puede_crear_o_modificar(usuario):
        raise SinPermiso("No tienes permiso para crear centros de ayuda")

    if usuario.rol == RolUsuario.ADMINISTRADOR and usuario.organizacion_id is None:
        raise SinPermiso("El administrador debe pertenecer a una organización")

    organizacion_id = usuario.organizacion_id if usuario.rol == RolUsuario.ADMINISTRADOR else None
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        organizacion_id = datos.organizacion_id

    centro = repo.crear(
        db,
        nombre=datos.nombre,
        tipo=datos.tipo,
        estado=datos.estado,
        direccion=datos.direccion,
        ubicacion=punto_desde_latlng(datos.lat, datos.lng),
        recursos_disponibles=datos.recursos_disponibles,
        gestionado_por=usuario.id,
        organizacion_id=organizacion_id,
    )
    db.commit()
    db.refresh(centro)
    return CentroAyudaOut.desde_modelo(centro)


def actualizar(db: Session, usuario: Usuario, centro_id: UUID, datos: CentroAyudaUpdate) -> CentroAyudaOut:
    centro = repo.obtener_por_id(db, centro_id)
    if centro is None:
        raise NoEncontrado("Centro de ayuda no encontrado", codigo="CENTRO_NO_ENCONTRADO")

    if not _puede_modificar_centro(usuario, centro):
        raise SinPermiso("No tienes permiso para modificar este centro de ayuda")

    cambios = {}
    if datos.nombre is not None:
        cambios['nombre'] = datos.nombre
    if datos.tipo is not None:
        cambios['tipo'] = datos.tipo
    if datos.estado is not None:
        cambios['estado'] = datos.estado
    if datos.direccion is not None:
        cambios['direccion'] = datos.direccion
    if datos.recursos_disponibles is not None:
        cambios['recursos_disponibles'] = datos.recursos_disponibles
    if datos.lat is not None and datos.lng is not None:
        cambios['ubicacion'] = punto_desde_latlng(datos.lat, datos.lng)
    elif datos.lat is not None or datos.lng is not None:
        raise DatosInvalidos("Debes enviar lat y lng juntos")
    if datos.organizacion_id is not None and es_super_admin(usuario):
        cambios['organizacion_id'] = datos.organizacion_id

    centro = repo.actualizar(db, centro, **cambios)
    db.commit()
    db.refresh(centro)
    return CentroAyudaOut.desde_modelo(centro)
