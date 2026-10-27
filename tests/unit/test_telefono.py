import pytest
from pydantic import BaseModel, ValidationError

from app.utils.telefono import Telefono, normalizar_telefono


class _Modelo(BaseModel):
    telefono: Telefono


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("+57 300 123 4567", "+573001234567"),  # formato que usa la app
        ("+573001234567", "+573001234567"),
        ("300-123-4567", "+573001234567"),  # celular colombiano sin indicativo
        ("+1 (415) 555-2671", "+14155552671"),
    ],
)
def test_normaliza_a_e164(entrada, esperado):
    assert _Modelo(telefono=entrada).telefono == esperado


@pytest.mark.parametrize("entrada", ["12345", "telefono", "+0573001234567", "7012345678"])
def test_rechaza_invalidos(entrada):
    with pytest.raises(ValidationError):
        _Modelo(telefono=entrada)


def test_fijo_colombiano_sin_indicativo():
    assert normalizar_telefono("605 570 0000") == "+576055700000"
    assert normalizar_telefono("(601) 234-5678") == "+576012345678"
