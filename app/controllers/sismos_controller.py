"""HTTP de sismos y check-ins: arma la respuesta y llama al service. Sin SQL ni reglas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.usuario import Usuario
from app.schemas.sismos_schema import (
    CheckInManualIn,
    CheckInOut,
    CheckInsEventoOut,
    RespuestaCheckInIn,
    SismoOut,
    SismoSimuladoIn,
)
from app.services import check_ins_service, sismos_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def listar_sismos(
    desde: datetime | None = None,
    magnitud_min: float | None = Query(default=None, ge=0, le=10),
    region: Literal["colombia", "mundo"] | None = Query(
        default=None, description="colombia, mundo (fuera de Colombia) o vacío para todos"
    ),
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[SismoOut]:
    items, total = sismos_service.listar(db, pag, desde=desde, magnitud_min=magnitud_min, region=region)
    return Pagina.crear([sismos_service.a_salida(db, usuario, e) for e in items], total, pag)


def obtener_sismo(evento_id: UUID, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> SismoOut:
    return sismos_service.a_salida(db, usuario, sismos_service.obtener(db, evento_id))


def simular_sismo(
    datos: SismoSimuladoIn | None = None, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> SismoOut:
    return sismos_service.a_salida(db, usuario, sismos_service.simular(db, usuario, datos or SismoSimuladoIn()))


def check_in_pendiente(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> CheckInOut | None:
    check_in = check_ins_service.pendiente(db, usuario)
    return CheckInOut.model_validate(check_in) if check_in else None


def activar_modo_emergencia(
    datos: CheckInManualIn | None = None, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> CheckInOut:
    return CheckInOut.model_validate(check_ins_service.activar_modo_emergencia(db, usuario, datos or CheckInManualIn()))


def responder_check_in(
    check_in_id: UUID,
    datos: RespuestaCheckInIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckInOut:
    return CheckInOut.model_validate(check_ins_service.responder(db, usuario, check_in_id, datos))


def check_ins_por_evento(evento_sismico_id: UUID | None = None, db: Session = Depends(get_db)) -> CheckInsEventoOut:
    return check_ins_service.por_evento(db, evento_sismico_id)
