"""HTTP de alertas: arma la respuesta y llama al service. Sin SQL ni reglas."""

from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import EstadoAlerta
from app.models.usuario import Usuario
from app.schemas.alertas_schema import AlertaCambiosIn, AlertaIn, AlertaOut
from app.services import alertas_service as service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def crear_alerta(datos: AlertaIn, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> AlertaOut:
    return service.a_salida(usuario, service.crear(db, usuario, datos))


def listar_alertas(
    estado: EstadoAlerta | None = None,
    lat: float | None = Query(default=None, ge=-90, le=90, description="Con lng: solo las que cubren ese punto"),
    lng: float | None = Query(default=None, ge=-180, le=180),
    solo_mi_organizacion: bool = False,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[AlertaOut]:
    items, total = service.listar(
        db, usuario, pag, estado=estado, lat=lat, lng=lng, solo_mi_organizacion=solo_mi_organizacion
    )
    return Pagina.crear([service.a_salida(usuario, a) for a in items], total, pag)


def obtener_alerta(alerta_id: UUID, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> AlertaOut:
    return service.a_salida(usuario, service.obtener(db, usuario, alerta_id))


def actualizar_alerta(
    alerta_id: UUID,
    datos: AlertaCambiosIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertaOut:
    return service.a_salida(usuario, service.actualizar(db, usuario, alerta_id, datos))


def cancelar_alerta(alerta_id: UUID, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> AlertaOut:
    return service.a_salida(usuario, service.cancelar(db, usuario, alerta_id))
