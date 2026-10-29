"""Derechos del titular (Ley 1581 de 2012, A6).

- Conocer: `exportar` devuelve todo lo que el sistema guarda de la persona.
- Suprimir: `eliminar_cuenta` anonimiza la cuenta. La fila del usuario se conserva porque de
  ella cuelgan solicitudes, reportes y fichas que siguen sirviendo a la emergencia, pero ya sin
  nombre, correo, teléfono ni ubicación. Se borran sus contactos y dispositivos, se cancelan sus
  tareas activas como voluntario y la cuenta queda bloqueada para siempre.
- Los consentimientos se conservan: son la prueba de que hubo autorización (art. 9).
"""

import secrets
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.excepciones import Conflicto, DatosInvalidos
from app.core.security import hash_password, verify_password
from app.models.enums import EstadoUsuario, RolUsuario
from app.models.usuario import Usuario
from app.repositories import consentimientos_repository, contactos_emergencia_repository, usuarios_repository
from app.repositories import datos_personales_repository as repo
from app.schemas.contactos_emergencia_schema import ContactoOut
from app.schemas.datos_personales_schema import (
    EliminarCuentaIn,
    MiDispositivoOut,
    MiPersonaReportadaOut,
    MiReporteOut,
    MiSolicitudOut,
    MisDatosOut,
    MiUbicacionOut,
)
from app.schemas.usuarios_schema import ConsentimientoOut, UsuarioOut

NOMBRE_ANONIMO = "Usuario eliminado"


def exportar(db: Session, usuario: Usuario) -> MisDatosOut:
    return MisDatosOut(
        perfil=UsuarioOut.model_validate(usuario),
        ubicacion=MiUbicacionOut.model_validate(usuario),
        consentimientos=[
            ConsentimientoOut.model_validate(c) for c in consentimientos_repository.listar_de_usuario(db, usuario.id)
        ],
        contactos_emergencia=[
            ContactoOut.model_validate(c) for c in contactos_emergencia_repository.listar_de_usuario(db, usuario.id)
        ],
        dispositivos=[MiDispositivoOut.model_validate(d) for d in repo.dispositivos(db, usuario.id)],
        solicitudes=[MiSolicitudOut.model_validate(s) for s in repo.solicitudes(db, usuario.id)],
        reportes=[MiReporteOut.model_validate(r) for r in repo.reportes(db, usuario.id)],
        personas_reportadas=[MiPersonaReportadaOut.model_validate(p) for p in repo.personas_reportadas(db, usuario.id)],
        generado_en=datetime.now(UTC),
    )


def eliminar_cuenta(db: Session, usuario: Usuario, datos: EliminarCuentaIn) -> None:
    if not verify_password(datos.password, usuario.password_hash):
        raise DatosInvalidos("La contraseña no es correcta", codigo="CONTRASENA_ACTUAL_INVALIDA")
    if (
        usuario.rol == RolUsuario.SUPER_ADMIN
        and usuario.estado == EstadoUsuario.ACTIVO
        and usuarios_repository.contar_super_admins_activos(db) <= 1
    ):
        raise Conflicto("El sistema no puede quedar sin un super admin activo", codigo="ULTIMO_SUPER_ADMIN")

    repo.cancelar_asignaciones_activas(db, usuario.id)
    contactos_emergencia_repository.eliminar_de_usuario(db, usuario.id)
    repo.borrar_dispositivos(db, usuario.id)
    usuarios_repository.actualizar(
        db,
        usuario,
        nombre=NOMBRE_ANONIMO,
        # Único y que nunca puede recibir correo (.invalid está reservado, RFC 2606)
        email=f"eliminado-{usuario.id.hex}@rescate360.invalid",
        telefono=None,
        ubicacion_actual=None,
        ubicacion_actualizada_en=None,
        # Contraseña aleatoria que nadie conoce: no se puede volver a entrar
        password_hash=hash_password(secrets.token_urlsafe(32)),
        codigo_activacion_hash=None,
        codigo_activacion_vence=None,
        codigo_recuperacion_hash=None,
        codigo_recuperacion_vence=None,
        estado=EstadoUsuario.BLOQUEADO,
        eliminado_en=datetime.now(UTC),
    )
    repo.limpiar_auditoria_de_usuario(db, usuario.id)
    db.commit()
