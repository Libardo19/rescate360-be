"""Rutas de centros de ayuda."""

from fastapi import APIRouter

from app.controllers import centros_ayuda_controller
from app.schemas.centros_ayuda_schema import CentroAyudaOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix='/centros-ayuda', tags=['centros-ayuda'])


router.get(
    '',
    response_model=Pagina[CentroAyudaOut],
    summary='Listar centros de ayuda (cercanos por lat/lng/radio)',
)(centros_ayuda_controller.listar_centros)


router.get(
    '/{centro_id}',
    response_model=CentroAyudaOut,
    summary='Detalle de un centro de ayuda',
)(centros_ayuda_controller.obtener_centro)


router.post(
    '',
    status_code=201,
    response_model=CentroAyudaOut,
    summary='Crear centro de ayuda (administrador de organización o super admin)',
)(centros_ayuda_controller.crear_centro)


router.patch(
    '/{centro_id}',
    response_model=CentroAyudaOut,
    summary='Actualizar centro de ayuda (administrador dueño de organización o super admin)',
)(centros_ayuda_controller.actualizar_centro)
