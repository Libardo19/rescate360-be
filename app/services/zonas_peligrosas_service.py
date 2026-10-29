from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import DatosInvalidos, NoEncontrado, SinPermiso
from app.middlewares.role_middleware import verificar_misma_organizacion
from app.models.enums import EstadoZona, RolUsuario
from app.models.usuario import Usuario
from app.models.zona_peligrosa import ZonaPeligrosa
from app.repositories import zonas_peligrosas_repository as repo
from app.schemas.zonas_peligrosas_schema import ZonaPeligrosaIn, ZonaPeligrosaOut, ZonaPeligrosaPatchIn
from app.utils.paginacion import Paginacion

VIGENTES = (EstadoZona.ACTIVA, EstadoZona.EN_MONITOREO)
ROLES_QUE_GESTIONAN = (RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN)
RADIO_BUSQUEDA_MAXIMO_M = 50_000


def es_propia(usuario: Usuario, zona: ZonaPeligrosa) -> bool:
    """True si el usuario puede modificar la zona: admin de su organización o super_admin."""
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        return True
    return (
        usuario.rol == RolUsuario.ADMINISTRADOR
        and usuario.organizacion_id is not None
        and zona.organizacion_id == usuario.organizacion_id
    )


def organizacion_visible(usuario: Usuario, alcance: Literal["organizacion", "todas"]) -> UUID | None:
    """Organización a la que se limita el listado, o None si ve todas.

    Solo el administrador se limita (y puede pedir alcance=todas). Ciudadano y voluntario ven todas
    las vigentes: son información de seguridad pública. El super_admin ve todas.
    """
    if usuario.rol == RolUsuario.ADMINISTRADOR and alcance == "organizacion":
        return usuario.organizacion_id
    return None


def estados_visibles(usuario: Usuario, estado: EstadoZona | None) -> tuple[EstadoZona, ...]:
    """Estados que entran en el listado.

    Por defecto, administrador y super_admin ven todos los estados (incluidas las inactivas);
    ciudadano y voluntario ven solo las vigentes. Un estado concreto solo lo puede pedir
    administrador o super_admin; para el resto ese pedido da vacío.
    """
    permitidos = tuple(EstadoZona) if usuario.rol in ROLES_QUE_GESTIONAN else VIGENTES
    if estado is None:
        return permitidos
    return (estado,) if estado in permitidos else ()


def _salida(usuario: Usuario, zona: ZonaPeligrosa, distancia_al_centro: float | None = None) -> ZonaPeligrosaOut:
    distancia = None
    if distancia_al_centro is not None:
        distancia = round(max(distancia_al_centro - zona.radio_m, 0.0), 1)  # hasta el borde del círculo
    return ZonaPeligrosaOut.model_validate(zona).model_copy(
        update={"propia": es_propia(usuario, zona), "distancia_m": distancia}
    )


def _organizacion_destino(db: Session, usuario: Usuario, solicitada: UUID | None) -> UUID | None:
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        if solicitada is not None and not repo.existe_organizacion(db, solicitada):
            raise DatosInvalidos("La organización indicada no existe", codigo="ORGANIZACION_NO_ENCONTRADA")
        return solicitada  # None = zona global
    if solicitada is not None and solicitada != usuario.organizacion_id:
        raise SinPermiso(
            "Solo el super administrador puede elegir otra organización", codigo="ZONA_ORGANIZACION_NO_PERMITIDA"
        )
    return usuario.organizacion_id


def crear_zona(db: Session, usuario: Usuario, datos: ZonaPeligrosaIn) -> ZonaPeligrosaOut:
    """Solo administrador y super_admin (se exige en la ruta)."""
    organizacion_id = _organizacion_destino(db, usuario, datos.organizacion_id)
    zona = repo.crear(
        db,
        nombre=datos.nombre,
        tipo_riesgo=datos.tipo_riesgo,
        nivel=datos.nivel,
        descripcion=datos.descripcion,
        estado=datos.estado,
        lat=datos.zona.lat,
        lng=datos.zona.lng,
        radio_m=datos.zona.radio_m,
        gestionado_por=usuario.id,
        organizacion_id=organizacion_id,
    )
    db.commit()
    return _salida(usuario, zona)


def listar_zonas(
    db: Session,
    usuario: Usuario,
    pag: Paginacion,
    *,
    lat: float | None,
    lng: float | None,
    radio_m: float,
    alcance: Literal["organizacion", "todas"],
    estado: EstadoZona | None,
) -> tuple[list[ZonaPeligrosaOut], int]:
    if (lat is None) != (lng is None):
        raise DatosInvalidos("Envía lat y lng juntos", codigo="UBICACION_INCOMPLETA")
    centro = (lat, lng) if lat is not None else None

    filas, total = repo.listar(
        db,
        pag,
        estados=estados_visibles(usuario, estado),
        organizacion_visible=organizacion_visible(usuario, alcance),
        centro=centro,
        radio_m=min(radio_m, RADIO_BUSQUEDA_MAXIMO_M),
    )
    return [_salida(usuario, zona, distancia) for zona, distancia in filas], total


def modificar_zona(
    db: Session, usuario: Usuario, zona_id: UUID, datos: ZonaPeligrosaPatchIn
) -> ZonaPeligrosaOut:
    """Solo administrador y super_admin (se exige en la ruta)."""
    zona = repo.obtener_por_id(db, zona_id)
    if zona is None:
        raise NoEncontrado("La zona no existe", codigo="ZONA_NO_ENCONTRADA")

    if usuario.rol != RolUsuario.SUPER_ADMIN:
        if zona.organizacion_id is None:
            raise SinPermiso("Solo el super administrador puede modificar zonas globales", codigo="ZONA_GLOBAL")
        verificar_misma_organizacion(usuario, zona.organizacion_id)

    cambios = datos.model_dump(exclude_unset=True)
    nueva_zona = cambios.pop("zona", None)
    circulo = (nueva_zona["lat"], nueva_zona["lng"], nueva_zona["radio_m"]) if nueva_zona else None

    zona = repo.actualizar(db, zona, cambios=cambios, circulo=circulo)
    db.commit()
    return _salida(usuario, zona)
