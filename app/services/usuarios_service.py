"""Lo que el usuario autenticado hace sobre su propia cuenta (`/usuarios/me/...`).

Reglas:
- La ubicación solo se guarda si el usuario autorizó el tratamiento de su ubicación
  (Ley 1581): la última fila de `consentimientos` de tipo `ubicacion` debe estar aceptada.
- Si retira esa autorización, se borra la ubicación guardada en ese mismo momento.
- La autorización de tratamiento de datos se da en el registro y no se retira aquí:
  retirarla equivale a eliminar la cuenta (A6, `DELETE /usuarios/me`).
"""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.excepciones import DatosInvalidos, SinPermiso
from app.models.consentimiento import Consentimiento
from app.models.dispositivo import Dispositivo
from app.models.enums import TipoConsentimiento
from app.models.usuario import Usuario
from app.repositories import consentimientos_repository, dispositivos_repository, usuarios_repository
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.schemas.usuarios_schema import ConsentimientoIn, DispositivoIn
from app.utils.geo import punto_desde_latlng


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
