"""Usuarios: la propia cuenta (`/usuarios/me/...`) y la gestión desde el panel (`/usuarios`).

Reglas de la propia cuenta:
- La ubicación solo se guarda si el usuario autorizó el tratamiento de su ubicación
  (Ley 1581): la última fila de `consentimientos` de tipo `ubicacion` debe estar aceptada.
- Si retira esa autorización, se borra la ubicación guardada en ese mismo momento.
- La autorización de tratamiento de datos se da en el registro y no se retira aquí:
  retirarla equivale a eliminar la cuenta (A6, `DELETE /usuarios/me`).

Reglas de la gestión (sección 4 de docs/PLAN_BACKEND.md):
- El administrador ve los usuarios de SU organización y solo gestiona voluntarios.
  Los ciudadanos no tienen organización: solo los ve el super admin.
- El super admin ve y gestiona a todos, pero no cambia su propio estado y el sistema
  nunca queda sin un super admin activo.
- Las altas son por invitación: la cuenta nace `en_espera` con un código de un solo uso
  que la persona canjea en `POST /auth/activar` (no hay envío de correos todavía).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.excepciones import Conflicto, DatosInvalidos, NoEncontrado, SinPermiso
from app.core.security import (
    contrasena_inutilizable,
    generar_codigo_activacion,
    hash_codigo,
    hash_password,
    verify_password,
)
from app.middlewares.role_middleware import alcance_organizacion, es_super_admin, verificar_misma_organizacion
from app.models.consentimiento import Consentimiento
from app.models.dispositivo import Dispositivo
from app.models.enums import EstadoUsuario, RolUsuario, TipoConsentimiento
from app.models.usuario import Usuario
from app.repositories import (
    consentimientos_repository,
    dispositivos_repository,
    organizaciones_repository,
    usuarios_repository,
)
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.schemas.usuarios_schema import (
    CambioPasswordIn,
    ConsentimientoIn,
    DispositivoIn,
    InvitacionOut,
    PerfilCambiosIn,
    UsuarioCambiosIn,
    UsuarioNuevoIn,
    UsuarioOut,
)
from app.utils.geo import punto_desde_latlng
from app.utils.paginacion import Paginacion


def autorizo_ubicacion(db: Session, usuario: Usuario) -> bool:
    consentimiento = consentimientos_repository.vigente(db, usuario.id, TipoConsentimiento.UBICACION)
    return consentimiento is not None and consentimiento.aceptado


def actualizar_ubicacion(db: Session, usuario: Usuario, ubicacion: LatLng) -> Usuario:
    if not autorizo_ubicacion(db, usuario):
        raise SinPermiso(
            "Debes autorizar el uso de tu ubicación para recibir alertas de tu zona",
            codigo="CONSENTIMIENTO_UBICACION_REQUERIDO",
        )
    usuario = usuarios_repository.actualizar_ubicacion(db, usuario, punto_desde_latlng(ubicacion.lat, ubicacion.lng))
    db.commit()
    return usuario


def registrar_consentimiento(db: Session, usuario: Usuario, datos: ConsentimientoIn, ip: str | None) -> Consentimiento:
    if datos.tipo == TipoConsentimiento.TRATAMIENTO_DATOS:
        raise DatosInvalidos(
            "La autorización de tratamiento de datos se da al registrarte; para retirarla elimina tu cuenta",
            codigo="CONSENTIMIENTO_NO_MODIFICABLE",
        )
    consentimiento = consentimientos_repository.registrar(
        db,
        usuario_id=usuario.id,
        tipo=datos.tipo,
        aceptado=datos.aceptado,
        version_politica=get_settings().version_politica_datos,
        ip=ip,
    )
    if datos.tipo == TipoConsentimiento.UBICACION and not datos.aceptado:
        usuarios_repository.borrar_ubicacion(db, usuario)
    db.commit()
    return consentimiento


def listar_consentimientos(db: Session, usuario: Usuario) -> list[Consentimiento]:
    return consentimientos_repository.listar_de_usuario(db, usuario.id)


def registrar_dispositivo(db: Session, usuario: Usuario, datos: DispositivoIn) -> Dispositivo:
    dispositivo = dispositivos_repository.registrar(
        db, usuario_id=usuario.id, token_push=datos.token_push, plataforma=datos.plataforma
    )
    db.commit()
    return dispositivo


def eliminar_dispositivo(db: Session, usuario: Usuario, token_push: str) -> None:
    """Al cerrar sesión. Idempotente: si el token no existe o es de otro usuario, no hace nada."""
    dispositivos_repository.eliminar(db, usuario_id=usuario.id, token_push=token_push)
    db.commit()


# --- Mi perfil ---


def actualizar_perfil(db: Session, usuario: Usuario, cambios: PerfilCambiosIn) -> Usuario:
    usuario = usuarios_repository.actualizar(db, usuario, **cambios.model_dump(exclude_unset=True))
    db.commit()
    return usuario


def cambiar_password(db: Session, usuario: Usuario, datos: CambioPasswordIn) -> None:
    if not verify_password(datos.password_actual, usuario.password_hash):
        raise DatosInvalidos("La contraseña actual no es correcta", codigo="CONTRASENA_ACTUAL_INVALIDA")
    if datos.password_nueva == datos.password_actual:
        raise DatosInvalidos("La contraseña nueva debe ser distinta de la actual", codigo="CONTRASENA_REPETIDA")
    # Si tenía un código de recuperación pendiente, deja de servir
    usuarios_repository.actualizar(
        db,
        usuario,
        password_hash=hash_password(datos.password_nueva),
        codigo_recuperacion_hash=None,
        codigo_recuperacion_vence=None,
    )
    db.commit()


# --- Alta por invitación (la usa también organizaciones_service para los administradores) ---


def _codigo_nuevo() -> tuple[str, str, datetime]:
    codigo = generar_codigo_activacion()
    vence = datetime.now(UTC) + timedelta(hours=get_settings().activacion_horas)
    return codigo, hash_codigo(codigo), vence


def crear_invitado(
    db: Session, *, datos: UsuarioNuevoIn, rol: RolUsuario, organizacion_id: UUID
) -> InvitacionOut:
    """Crea la cuenta en `en_espera`, sin contraseña utilizable, y devuelve el código UNA vez."""
    if usuarios_repository.obtener_por_email(db, datos.email):
        raise Conflicto("Ya existe una cuenta con ese correo", codigo="EMAIL_YA_REGISTRADO")

    codigo, codigo_hash, vence = _codigo_nuevo()
    try:
        usuario = usuarios_repository.crear(
            db,
            nombre=datos.nombre,
            email=datos.email,
            telefono=datos.telefono,
            password_hash=contrasena_inutilizable(),
            rol=rol,
            estado=EstadoUsuario.EN_ESPERA,
            organizacion_id=organizacion_id,
            codigo_activacion_hash=codigo_hash,
            codigo_activacion_vence=vence,
        )
    except IntegrityError:  # dos altas simultáneas con el mismo correo
        db.rollback()
        raise Conflicto("Ya existe una cuenta con ese correo", codigo="EMAIL_YA_REGISTRADO") from None
    db.commit()
    db.refresh(usuario)  # trae el código USR-xxx que asignó la BD
    return InvitacionOut(usuario=UsuarioOut.model_validate(usuario), codigo_activacion=codigo, vence_en=vence)


def _organizacion_para_alta(db: Session, actor: Usuario, organizacion_id: UUID | None) -> UUID:
    """El admin siempre crea en su organización; el super admin debe decir en cuál."""
    if not es_super_admin(actor):
        if organizacion_id is not None and organizacion_id != actor.organizacion_id:
            raise SinPermiso("Solo puedes crear voluntarios en tu organización", codigo="FUERA_DE_ALCANCE")
        return actor.organizacion_id

    if organizacion_id is None:
        raise DatosInvalidos("Indica la organización del voluntario", codigo="ORGANIZACION_REQUERIDA")
    organizacion = organizaciones_repository.obtener_por_id(db, organizacion_id)
    if organizacion is None:
        raise NoEncontrado("La organización no existe", codigo="ORGANIZACION_NO_ENCONTRADA")
    if not organizacion.activa:
        raise Conflicto("La organización está desactivada", codigo="ORGANIZACION_INACTIVA")
    return organizacion.id


def crear_voluntario(db: Session, actor: Usuario, datos: UsuarioNuevoIn) -> InvitacionOut:
    organizacion_id = _organizacion_para_alta(db, actor, datos.organizacion_id)
    return crear_invitado(db, datos=datos, rol=RolUsuario.VOLUNTARIO, organizacion_id=organizacion_id)


# --- Gestión desde el panel ---


def listar_usuarios(
    db: Session,
    actor: Usuario,
    pag: Paginacion,
    *,
    rol: RolUsuario | None,
    estado: EstadoUsuario | None,
    q: str | None,
    organizacion_id: UUID | None,
) -> tuple[list[Usuario], int]:
    alcance = alcance_organizacion(actor)  # None = super admin
    if alcance is not None:
        organizacion_id = alcance  # el admin no puede pedir otra organización
    return usuarios_repository.listar(db, pag, organizacion_id=organizacion_id, rol=rol, estado=estado, q=q)


def obtener_usuario(db: Session, actor: Usuario, usuario_id: UUID) -> Usuario:
    usuario = usuarios_repository.obtener_por_id(db, usuario_id)
    if usuario is None:
        raise NoEncontrado("El usuario no existe", codigo="USUARIO_NO_ENCONTRADO")
    verificar_misma_organizacion(actor, usuario.organizacion_id)
    return usuario


def _verificar_gestionable(actor: Usuario, usuario: Usuario) -> None:
    """El admin solo gestiona voluntarios (los administradores los gestiona el super admin)."""
    if not es_super_admin(actor) and usuario.rol != RolUsuario.VOLUNTARIO:
        raise SinPermiso("Solo puedes gestionar voluntarios de tu organización", codigo="USUARIO_NO_GESTIONABLE")


def _validar_cambio_de_estado(db: Session, actor: Usuario, usuario: Usuario, nuevo: EstadoUsuario) -> EstadoUsuario:
    """Devuelve el estado que realmente queda (puede ser `en_espera` si nunca activó la cuenta)."""
    if usuario.id == actor.id:
        raise Conflicto("No puedes cambiar el estado de tu propia cuenta", codigo="AUTOPROTECCION")

    invitacion_pendiente = usuario.codigo_activacion_hash is not None
    if nuevo == EstadoUsuario.ACTIVO and invitacion_pendiente:
        if usuario.estado == EstadoUsuario.EN_ESPERA:
            raise Conflicto("La cuenta se activa con su código de activación", codigo="CUENTA_SIN_ACTIVAR")
        return EstadoUsuario.EN_ESPERA  # se desbloquea, pero sigue esperando que la active

    if (
        nuevo == EstadoUsuario.BLOQUEADO
        and usuario.rol == RolUsuario.SUPER_ADMIN
        and usuario.estado == EstadoUsuario.ACTIVO
        and usuarios_repository.contar_super_admins_activos(db) <= 1
    ):
        raise Conflicto("El sistema no puede quedar sin un super admin activo", codigo="ULTIMO_SUPER_ADMIN")
    return nuevo


def actualizar_usuario(db: Session, actor: Usuario, usuario_id: UUID, cambios: UsuarioCambiosIn) -> Usuario:
    usuario = obtener_usuario(db, actor, usuario_id)
    _verificar_gestionable(actor, usuario)

    campos = cambios.model_dump(exclude_unset=True)
    if "email" in campos:
        if campos["email"] is None:
            raise DatosInvalidos("El correo no puede quedar vacío", codigo="EMAIL_REQUERIDO")
        otro = usuarios_repository.obtener_por_email(db, campos["email"])
        if otro is not None and otro.id != usuario.id:
            raise Conflicto("Ya existe una cuenta con ese correo", codigo="EMAIL_YA_REGISTRADO")
    if "nombre" in campos and campos["nombre"] is None:
        raise DatosInvalidos("El nombre no puede quedar vacío", codigo="NOMBRE_REQUERIDO")
    if campos.get("estado") is not None:
        campos["estado"] = _validar_cambio_de_estado(db, actor, usuario, campos["estado"])
    elif "estado" in campos:
        del campos["estado"]

    try:
        usuario = usuarios_repository.actualizar(db, usuario, **campos)
    except IntegrityError:  # el correo lo tomó otra cuenta al mismo tiempo
        db.rollback()
        raise Conflicto("Ya existe una cuenta con ese correo", codigo="EMAIL_YA_REGISTRADO") from None
    db.commit()
    return usuario


def regenerar_codigo_activacion(db: Session, actor: Usuario, usuario_id: UUID) -> InvitacionOut:
    """Para cuando el código venció o se perdió. El anterior deja de servir."""
    usuario = obtener_usuario(db, actor, usuario_id)
    _verificar_gestionable(actor, usuario)
    if usuario.estado != EstadoUsuario.EN_ESPERA:
        raise Conflicto("La cuenta no está esperando activación", codigo="CUENTA_NO_PENDIENTE")

    codigo, codigo_hash, vence = _codigo_nuevo()
    usuario = usuarios_repository.actualizar(
        db, usuario, codigo_activacion_hash=codigo_hash, codigo_activacion_vence=vence
    )
    db.commit()
    return InvitacionOut(usuario=UsuarioOut.model_validate(usuario), codigo_activacion=codigo, vence_en=vence)
