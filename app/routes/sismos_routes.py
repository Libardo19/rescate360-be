"""Rutas de sismos (B8) y del "¿Estás bien?" (check-ins)."""

from fastapi import APIRouter, Depends

from app.controllers import sismos_controller
from app.middlewares.role_middleware import ROLES_ADMIN, require_role
from app.models.enums import RolUsuario
from app.schemas.sismos_schema import CheckInOut, CheckInsEventoOut, SismoOut
from app.utils.paginacion import Pagina

router = APIRouter(tags=["sismos"])

# --- sismos ---

router.get(
    "/sismos", response_model=Pagina[SismoOut], summary="Sismos de todo el mundo; region=colombia o region=mundo para filtrar (USGS/SGC)"
)(sismos_controller.listar_sismos)

# /simular va antes de /{evento_id} para que no se lea como un id
router.post(
    "/sismos/simular",
    status_code=201,
    response_model=SismoOut,
    summary="Simulacro: crea un sismo falso con su alerta y sus check-ins (super admin, solo en local)",
    dependencies=[Depends(require_role(RolUsuario.SUPER_ADMIN))],
)(sismos_controller.simular_sismo)

router.get("/sismos/{evento_id}", response_model=SismoOut, summary="Detalle (con la distancia a mi ubicación)")(
    sismos_controller.obtener_sismo
)

# --- "¿Estás bien?" ---

router.get(
    "/check-ins/pendiente",
    response_model=CheckInOut | None,
    summary="Mi \"¿Estás bien?\" pendiente (la app lo consulta al abrir y cada minuto)",
)(sismos_controller.check_in_pendiente)

router.post(
    "/check-ins",
    status_code=201,
    response_model=CheckInOut,
    summary="Modo emergencia: que me pregunten si estoy bien y avisen a mis contactos si no respondo",
)(sismos_controller.activar_modo_emergencia)

router.post(
    "/check-ins/{check_in_id}/responder",
    response_model=CheckInOut,
    summary="Responder: a_salvo, o necesito_ayuda (crea un SOS)",
)(sismos_controller.responder_check_in)

router.get(
    "/check-ins",
    response_model=CheckInsEventoOut,
    summary="Quién está a salvo, quién pidió ayuda y quién no respondió (administrador)",
    dependencies=[Depends(require_role(*ROLES_ADMIN))],
)(sismos_controller.check_ins_por_evento)
