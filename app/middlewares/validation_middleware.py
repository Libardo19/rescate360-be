"""Errores de validación de Pydantic (422) en el formato del contrato y en español.

    {
      "detalle": "Los datos enviados no son válidos",
      "codigo": "DATOS_INVALIDOS",
      "errores": [{"campo": "email", "mensaje": "Correo electrónico inválido"}]
    }
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _mensaje(error: dict) -> str:
    tipo = error.get("type", "")
    ctx = error.get("ctx") or {}
    if tipo == "missing":
        return "Campo obligatorio"
    if tipo == "string_too_short":
        return f"Debe tener al menos {ctx.get('min_length')} caracteres"
    if tipo == "string_too_long":
        return f"Debe tener máximo {ctx.get('max_length')} caracteres"
    if tipo == "string_pattern_mismatch":
        return "Formato inválido"
    if tipo in ("greater_than_equal", "greater_than"):
        return f"Debe ser mayor o igual a {ctx.get('ge', ctx.get('gt'))}"
    if tipo in ("less_than_equal", "less_than"):
        return f"Debe ser menor o igual a {ctx.get('le', ctx.get('lt'))}"
    if tipo in ("int_parsing", "int_type"):
        return "Debe ser un número entero"
    if tipo in ("float_parsing", "float_type"):
        return "Debe ser un número"
    if tipo in ("bool_parsing", "bool_type"):
        return "Debe ser verdadero o falso"
    if tipo == "uuid_parsing":
        return "Identificador inválido"
    if tipo == "enum":
        return f"Valor no permitido. Opciones: {ctx.get('expected')}"
    if tipo in ("datetime_parsing", "datetime_from_date_parsing", "date_parsing"):
        return "Fecha inválida"
    if tipo == "value_error":
        # Mensajes de nuestros validadores y del validador de correo
        mensaje = error.get("msg", "").removeprefix("Value error, ")
        if "email address" in mensaje:
            return "Correo electrónico inválido"
        return mensaje
    return error.get("msg", "Valor inválido")


def _campo(loc: tuple) -> str:
    # loc = ("body", "email") o ("query", "pagina"); se quita el origen.
    partes = [str(p) for p in loc[1:]] if len(loc) > 1 else [str(p) for p in loc]
    return ".".join(partes)


async def manejar_error_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    errores = [{"campo": _campo(e["loc"]), "mensaje": _mensaje(e)} for e in exc.errors()]
    return JSONResponse(
        {"detalle": "Los datos enviados no son válidos", "codigo": "DATOS_INVALIDOS", "errores": errores},
        status_code=422,
    )
