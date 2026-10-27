"""Reglas puras de asignaciones, sin base de datos."""

import pytest
from pydantic import ValidationError

from app.models.enums import EstadoAsignacion, EstadoSolicitud
from app.schemas.asignaciones_schema import AsignacionEstadoIn
from app.services.asignaciones_service import ESTADOS_CERRADOS, estado_solicitud_tras_cambio

P, E, A, C = (
    EstadoSolicitud.PENDIENTE,
    EstadoSolicitud.EN_PROCESO,
    EstadoSolicitud.ATENDIDA,
    EstadoSolicitud.CANCELADA,
)
FIN, CAN = EstadoAsignacion.FINALIZADA, EstadoAsignacion.CANCELADA


@pytest.mark.parametrize(
    "estado_solicitud, nuevo, activas, esperado",
    [
        (E, FIN, 0, A),  # finalizar atiende el caso
        (E, FIN, 2, A),  # aunque otros sigan activos
        (P, FIN, 0, A),
        (A, FIN, 0, None),  # ya atendida: nada que cambiar
        (C, FIN, 0, None),  # cancelada por un admin: no se revive
        (E, CAN, 0, P),  # cancelar a la última persona activa devuelve el caso a pendiente
        (E, CAN, 1, None),  # todavía queda alguien activo
        (P, CAN, 0, None),
        (A, CAN, 0, None),
        (C, CAN, 0, None),
    ],
)
def test_estado_solicitud_tras_cambio(estado_solicitud, nuevo, activas, esperado):
    assert estado_solicitud_tras_cambio(estado_solicitud, nuevo, activas) == esperado


def test_estados_cerrados():
    assert set(ESTADOS_CERRADOS) == {A, C}


@pytest.mark.parametrize("estado", [EstadoAsignacion.FINALIZADA, EstadoAsignacion.CANCELADA])
def test_schema_acepta_estados_de_cierre(estado):
    assert AsignacionEstadoIn(estado=estado).estado == estado


def test_schema_rechaza_activa():
    with pytest.raises(ValidationError):
        AsignacionEstadoIn(estado=EstadoAsignacion.ACTIVA)
