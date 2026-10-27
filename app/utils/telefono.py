"""Teléfonos en formato E.164 (+573001234567).

La app envía "+57 300 123 4567"; se quitan espacios, guiones y paréntesis antes de
validar. Si llega un número colombiano de 10 dígitos sin indicativo, se le agrega +57:
celulares (3xx) y fijos (60x, marcación nacional desde 2021; ej. 605 para el Cesar).

    class ContactoIn(BaseModel):
        telefono: Telefono
"""

import re
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_SEPARADORES = re.compile(r"[\s\-().]")


def normalizar_telefono(valor: object) -> object:
    if not isinstance(valor, str):
        return valor
    limpio = _SEPARADORES.sub("", valor)
    if re.fullmatch(r"(3\d|60)\d{8}", limpio):  # celular o fijo colombiano sin indicativo
        limpio = "+57" + limpio
    return limpio


def validar_e164(valor: str) -> str:
    if not _E164.match(valor):
        raise ValueError("Teléfono inválido. Usa el formato internacional, por ejemplo +573001234567")
    return valor


Telefono = Annotated[str, BeforeValidator(normalizar_telefono), AfterValidator(validar_e164)]
