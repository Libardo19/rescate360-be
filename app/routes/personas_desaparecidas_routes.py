"""Rutas de personas desaparecidas (A5)."""

from fastapi import APIRouter

from app.controllers import personas_desaparecidas_controller
from app.schemas.personas_desaparecidas_schema import PersonaOut
from app.utils.paginacion import Pagina

router = APIRouter(prefix="/personas-desaparecidas", tags=["personas desaparecidas"])

router.post(
    "", status_code=201, response_model=PersonaOut, summary="Reportar una persona desaparecida (multipart, con foto)"
)(personas_desaparecidas_controller.crear_persona)

router.get(
    "", response_model=Pagina[PersonaOut], summary="Listar fichas (búsqueda por nombre, filtro por estado)"
)(personas_desaparecidas_controller.listar_personas)

router.get(
    "/{persona_id}", response_model=PersonaOut, summary="Detalle de una ficha (con contacto y aviso legal)"
)(personas_desaparecidas_controller.obtener_persona)

router.patch(
    "/{persona_id}", response_model=PersonaOut, summary="Editar la ficha (quien la reportó o un administrador)"
)(personas_desaparecidas_controller.editar_persona)

router.patch(
    "/{persona_id}/estado",
    response_model=PersonaOut,
    summary="Marcar como encontrada o volver a buscando (quien la reportó o un administrador)",
)(personas_desaparecidas_controller.cambiar_estado)
