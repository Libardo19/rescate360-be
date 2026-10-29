"""Alertas por zona (B3).

Reglas de acceso:
- Las alertas activas son información de seguridad pública: las ve cualquiera con sesión.
  Con `lat` y `lng` se piden solo las que cubren ese punto (las que "me afectan").
- Administrador y super admin ven también las expiradas y canceladas.
- Publicar: administrador (en su organización) o super admin (en la que elija, o global).
- Editar y cancelar: administrador de la organización de la alerta o super admin.

Al publicarla se encola `notificar_alerta_zona`: push a quienes estén dentro del círculo.
Vence sola con `expira_en` (job expirar_alertas).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import Conflicto, DatosInvalidos, NoEncontrado, SinPermiso
from app.jobs import encolar as cola
from app.jobs.eventos.notificar_alerta_zona import notificar_alerta_zona
from app.middlewares.role_middleware import ROLES_ADMIN, verificar_misma_organizacion
from app.models.alerta import Alerta
from app.models.enums import EstadoAlerta, NivelAlerta, RolUsuario
from app.models.usuario import Usuario
from app.repositories import alertas_repository as repo
from app.repositories import organizaciones_repository
from app.schemas.alertas_schema import AlertaCambiosIn, AlertaIn, AlertaOut
from app.utils.paginacion import Paginacion


def es_propia(usuario: Usuario, alerta: Alerta) -> bool:
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        return True
    return (
        usuario.rol == RolUsuario.ADMINISTRADOR
        and usuario.organizacion_id is not None
        and alerta.organizacion_id == usuario.organizacion_id
    )


def a_salida(usuario: Usuario, alerta: Alerta) -> AlertaOut:
    return AlertaOut.model_validate(alerta).model_copy(update={"propia": es_propia(usuario, alerta)})


def _organizacion_destino(db: Session, usuario: Usuario, solicitada: UUID | None) -> UUID | None:
    if usuario.rol == RolUsuario.SUPER_ADMIN:
        if solicitada is not None and organizaciones_repository.obtener_por_id(db, solicitada) is None:
            raise DatosInvalidos("La organización indicada no existe", codigo="ORGANIZACION_NO_ENCONTRADA")
        return solicitada  # None = alerta global
    if solicitada is not None and solicitada != usuario.organizacion_id:
        raise SinPermiso(
            "Solo el super admin puede publicar en otra organización", codigo="ALERTA_ORGANIZACION_NO_PERMITIDA"
        )
    return usuario.organizacion_id


def publicar(
    db: Session,
    *,
    creado_por: UUID,
    organizacion_id: UUID | None,
    titulo: str,
    tipo: str,
    mensaje: str,
    nivel: NivelAlerta,
    lat: float,
    lng: float,
    radio_m: float,
    horas_vigencia: int,
    origen: str = "manual",
) -> Alerta:
    """Crea la alerta y encola el push. La usa también el job de sismos (origen="sismo")."""
    alerta = repo.crear(
        db,
        titulo=titulo,
        tipo=tipo,
        mensaje=mensaje,
        nivel=nivel,
        lat=lat,
        lng=lng,
        radio_m=radio_m,
        expira_en=datetime.now(UTC) + timedelta(hours=horas_vigencia),
        creado_por=creado_por,
        organizacion_id=organizacion_id,
        origen=origen,
    )
    db.commit()
    # Después del commit, para que el worker encuentre la fila
    cola.encolar(notificar_alerta_zona, str(alerta.id))
    return alerta


def crear(db: Session, usuario: Usuario, datos: AlertaIn) -> Alerta:
    """Solo administrador y super admin (se exige en la ruta)."""
    return publicar(
        db,
        creado_por=usuario.id,
        organizacion_id=_organizacion_destino(db, usuario, datos.organizacion_id),
        titulo=datos.titulo,
        tipo=datos.tipo.lower(),
        mensaje=datos.mensaje,
        nivel=datos.nivel,
        lat=datos.zona.lat,
        lng=datos.zona.lng,
        radio_m=datos.zona.radio_m,
        horas_vigencia=datos.horas_vigencia,
    )


def listar(
    db: Session,
    usuario: Usuario,
    pag: Paginacion,
    *,
    estado: EstadoAlerta | None,
    lat: float | None,
    lng: float | None,
    solo_mi_organizacion: bool,
) -> tuple[list[Alerta], int]:
    if (lat is None) != (lng is None):
        raise DatosInvalidos("Envía lat y lng juntos, o ninguno", codigo="UBICACION_INCOMPLETA")
    gestiona = usuario.rol in ROLES_ADMIN
    if estado is None:
        estados = tuple(EstadoAlerta) if gestiona else (EstadoAlerta.ACTIVA,)
    else:
        # Ciudadano y voluntario solo ven las activas: pedir otro estado da vacío
        estados = (estado,) if gestiona or estado == EstadoAlerta.ACTIVA else ()
    organizacion_id = (
        usuario.organizacion_id if solo_mi_organizacion and usuario.rol == RolUsuario.ADMINISTRADOR else None
    )
    return repo.listar(
        db,
        pag,
        estados=estados,
        punto=(lat, lng) if lat is not None else None,
        organizacion_id=organizacion_id,
    )


def obtener(db: Session, usuario: Usuario, alerta_id: UUID) -> Alerta:
    alerta = repo.obtener_por_id(db, alerta_id)
    if alerta is None or (alerta.estado != EstadoAlerta.ACTIVA and usuario.rol not in ROLES_ADMIN):
        raise NoEncontrado("La alerta no existe", codigo="ALERTA_NO_ENCONTRADA")
    return alerta


def _para_gestionar(db: Session, usuario: Usuario, alerta_id: UUID) -> Alerta:
    alerta = repo.bloquear(db, alerta_id)
    if alerta is None:
        raise NoEncontrado("La alerta no existe", codigo="ALERTA_NO_ENCONTRADA")
    if usuario.rol != RolUsuario.SUPER_ADMIN:
        verificar_misma_organizacion(usuario, alerta.organizacion_id)
    if alerta.estado != EstadoAlerta.ACTIVA:
        raise Conflicto("La alerta ya no está activa", codigo="ALERTA_NO_ACTIVA")
    return alerta


def actualizar(db: Session, usuario: Usuario, alerta_id: UUID, cambios: AlertaCambiosIn) -> Alerta:
    alerta = _para_gestionar(db, usuario, alerta_id)
    campos = cambios.model_dump(exclude_unset=True)
    if "horas_vigencia" in campos:
        campos["expira_en"] = datetime.now(UTC) + timedelta(hours=campos.pop("horas_vigencia"))
    alerta = repo.actualizar(db, alerta, **campos)
    db.commit()
    return alerta


def cancelar(db: Session, usuario: Usuario, alerta_id: UUID) -> Alerta:
    alerta = repo.actualizar(db, _para_gestionar(db, usuario, alerta_id), estado=EstadoAlerta.CANCELADA)
    db.commit()
    return alerta
