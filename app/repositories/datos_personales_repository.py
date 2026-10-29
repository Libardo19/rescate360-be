"""Consultas de los derechos del titular: todo lo suyo, de varias tablas, para exportar o suprimir."""

from uuid import UUID

from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.models.asignacion import Asignacion
from app.models.dispositivo import Dispositivo
from app.models.enums import EstadoAsignacion
from app.models.persona_desaparecida import PersonaDesaparecida
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda

# Datos personales que se borran también de la historia de auditoría de la fila del usuario
CAMPOS_PERSONALES = ("nombre", "email", "telefono", "ubicacion_actual")


def solicitudes(db: Session, usuario_id: UUID) -> list[SolicitudAyuda]:
    consulta = select(SolicitudAyuda).where(SolicitudAyuda.usuario_id == usuario_id).order_by(SolicitudAyuda.creado_en)
    return list(db.scalars(consulta))


def reportes(db: Session, usuario_id: UUID) -> list[Reporte]:
    consulta = select(Reporte).where(Reporte.usuario_id == usuario_id).order_by(Reporte.creado_en)
    return list(db.scalars(consulta))


def personas_reportadas(db: Session, usuario_id: UUID) -> list[PersonaDesaparecida]:
    consulta = (
        select(PersonaDesaparecida)
        .where(PersonaDesaparecida.reportado_por == usuario_id)
        .order_by(PersonaDesaparecida.creado_en)
    )
    return list(db.scalars(consulta))


def dispositivos(db: Session, usuario_id: UUID) -> list[Dispositivo]:
    consulta = select(Dispositivo).where(Dispositivo.usuario_id == usuario_id).order_by(Dispositivo.creado_en)
    return list(db.scalars(consulta))


def borrar_dispositivos(db: Session, usuario_id: UUID) -> None:
    db.execute(delete(Dispositivo).where(Dispositivo.usuario_id == usuario_id))


def cancelar_asignaciones_activas(db: Session, voluntario_id: UUID) -> None:
    db.execute(
        update(Asignacion)
        .where(Asignacion.voluntario_id == voluntario_id, Asignacion.estado_asignacion == EstadoAsignacion.ACTIVA)
        .values(estado_asignacion=EstadoAsignacion.CANCELADA)
    )


def limpiar_auditoria_de_usuario(db: Session, usuario_id: UUID) -> None:
    """Quita nombre, correo, teléfono y ubicación de la historia del usuario en `auditoria`.

    El registro de qué pasó y cuándo se conserva; solo se van los datos personales.
    Se llama después del UPDATE que anonimiza, para limpiar también la fila que ese UPDATE generó.
    """
    db.flush()
    db.execute(
        text(
            """
            UPDATE auditoria
            SET datos_anteriores = datos_anteriores - CAST(:campos AS text[]),
                datos_nuevos = datos_nuevos - CAST(:campos AS text[])
            WHERE tabla = 'usuarios' AND registro_id = :usuario_id
            """
        ),
        {"campos": list(CAMPOS_PERSONALES), "usuario_id": usuario_id},
    )
