"""Dashboard por rol (A7, solo backend).

- Voluntario: los números de su organización + sus tareas activas.
- Administrador: su organización.
- Super admin: todo el sistema + totales por organización + casos sin organización.
- El ciudadano no tiene dashboard (se exige en la ruta).
"""

from sqlalchemy.orm import Session

from app.middlewares.role_middleware import alcance_organizacion, es_super_admin
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.repositories import dashboard_repository as repo
from app.schemas.dashboard_schema import ActividadOut, DashboardOut, ResumenOut, TotalesOrganizacionOut
from app.schemas.reportes_schema import etiqueta_tipo
from app.services.mapa_service import ETIQUETAS_SOLICITUD

LIMITE_RECIENTES = 10
LARGO_DETALLE = 80


def _corto(texto: str) -> str:
    return texto if len(texto) <= LARGO_DETALLE else texto[: LARGO_DETALLE - 1].rstrip() + "…"


def _recientes(db: Session, organizacion_id) -> list[ActividadOut]:
    actividad = [
        ActividadOut(
            id=s.id,
            tipo="solicitud",
            titulo=ETIQUETAS_SOLICITUD.get(s.tipo.value, "Solicitud de ayuda"),
            detalle=_corto(s.descripcion),
            estado=s.estado.value,
            creado_en=s.creado_en,
        )
        for s in repo.solicitudes_recientes(db, organizacion_id, LIMITE_RECIENTES)
    ] + [
        ActividadOut(
            id=r.id,
            tipo="reporte",
            titulo=etiqueta_tipo(r.tipo),
            detalle=_corto(r.descripcion),
            estado=r.estado.value,
            creado_en=r.creado_en,
        )
        for r in repo.reportes_recientes(db, organizacion_id, LIMITE_RECIENTES)
    ]
    actividad.sort(key=lambda a: a.creado_en, reverse=True)
    return actividad[:LIMITE_RECIENTES]


def obtener(db: Session, usuario: Usuario) -> DashboardOut:
    organizacion_id = alcance_organizacion(usuario)
    global_ = es_super_admin(usuario)
    resumen = ResumenOut(
        reportes_pendientes=repo.reportes_pendientes(db, organizacion_id),
        solicitudes_activas=repo.solicitudes_activas(db, organizacion_id),
        alertas_activas=repo.alertas_activas(db, organizacion_id),
        centros_registrados=repo.centros_registrados(db, organizacion_id),
        personas_buscando=repo.personas_buscando(db),
        voluntarios_activos=repo.voluntarios_activos(db, organizacion_id),
        mis_tareas_activas=repo.tareas_activas_de(db, usuario.id) if usuario.rol == RolUsuario.VOLUNTARIO else None,
        casos_sin_organizacion=repo.sin_organizacion(db) if global_ else None,
    )
    return DashboardOut(
        alcance="global" if global_ else "organizacion",
        resumen=resumen,
        recientes=_recientes(db, organizacion_id),
        por_organizacion=(
            [TotalesOrganizacionOut(**fila) for fila in repo.totales_por_organizacion(db)] if global_ else None
        ),
    )
