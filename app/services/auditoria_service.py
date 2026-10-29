"""Historial de auditoría (A7). Solo lectura.

Alcance:
- Super admin: todo el sistema.
- Administrador: lo que hicieron los usuarios de su organización.
- Voluntario y ciudadano: no tienen acceso (se exige en la ruta).

Las filas las escribe el trigger fn_auditoria(), que ya quita contraseñas y códigos.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.middlewares.role_middleware import alcance_organizacion
from app.models.auditoria import Auditoria
from app.models.enums import OperacionAuditoria
from app.models.usuario import Usuario
from app.repositories import auditoria_repository as repo
from app.schemas.auditoria_schema import MODULOS, VERBOS, ActorOut, AuditoriaOut
from app.utils.paginacion import Paginacion

# Columnas que cambian solas en cada UPDATE: no dicen nada en el texto de la acción
_RUIDO = {"actualizado_en"}


def campos_cambiados(fila: Auditoria) -> list[str] | None:
    """El trigger no llena `campos_modificados`: en un UPDATE se calculan comparando antes y después."""
    if fila.campos_modificados:
        return fila.campos_modificados
    if fila.operacion != OperacionAuditoria.UPDATE or fila.datos_anteriores is None or fila.datos_nuevos is None:
        return None
    antes, despues = fila.datos_anteriores, fila.datos_nuevos
    return sorted(c for c in antes.keys() | despues.keys() if antes.get(c) != despues.get(c))


def _accion(fila: Auditoria, modulo: str, campos: list[str] | None) -> str:
    texto = f"{VERBOS[fila.operacion]} {modulo}"
    visibles = [c for c in (campos or []) if c not in _RUIDO]
    return f"{texto} ({', '.join(visibles)})" if visibles else texto


def a_salida(fila: Auditoria, actor: Usuario | None) -> AuditoriaOut:
    modulo = MODULOS.get(fila.tabla, fila.tabla)
    campos = campos_cambiados(fila)
    return AuditoriaOut(
        id=fila.id,
        tabla=fila.tabla,
        modulo=modulo,
        registro_id=fila.registro_id,
        operacion=fila.operacion,
        actor=ActorOut(id=actor.id, nombre=actor.nombre) if actor else None,
        accion=_accion(fila, modulo, campos),
        campos_modificados=campos,
        datos_anteriores=fila.datos_anteriores,
        datos_nuevos=fila.datos_nuevos,
        creado_en=fila.creado_en,
    )


def listar(
    db: Session,
    usuario: Usuario,
    pag: Paginacion,
    *,
    tabla: str | None,
    registro_id: UUID | None,
    usuario_id: UUID | None,
    operacion: OperacionAuditoria | None,
    desde: datetime | None,
    hasta: datetime | None,
) -> tuple[list[AuditoriaOut], int]:
    filas, total = repo.listar(
        db,
        pag,
        organizacion_id=alcance_organizacion(usuario),
        tabla=tabla,
        registro_id=registro_id,
        usuario_id=usuario_id,
        operacion=operacion,
        desde=desde,
        hasta=hasta,
    )
    return [a_salida(fila, actor) for fila, actor in filas], total
