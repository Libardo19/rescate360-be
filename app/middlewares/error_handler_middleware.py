"""Convierte cualquier error en el formato del contrato: `{"detalle": "...", "codigo": "..."}`."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.excepciones import ErrorNegocio
from app.middlewares.validation_middleware import manejar_error_validacion

logger = logging.getLogger(__name__)


def _respuesta(status_code: int, detalle: str, codigo: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse({"detalle": detalle, "codigo": codigo}, status_code=status_code, headers=headers)


async def manejar_error_negocio(request: Request, exc: ErrorNegocio) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return _respuesta(exc.status_code, exc.detalle, exc.codigo, headers)


async def manejar_error_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detalle = exc.detail if isinstance(exc.detail, str) else "Error en la petición"
    return _respuesta(exc.status_code, detalle, f"HTTP_{exc.status_code}", getattr(exc, "headers", None))


async def manejar_error_inesperado(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return _respuesta(500, "Error interno del servidor", "ERROR_INTERNO")


def registrar_manejadores_errores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorNegocio, manejar_error_negocio)
    app.add_exception_handler(StarletteHTTPException, manejar_error_http)
    app.add_exception_handler(RequestValidationError, manejar_error_validacion)
    app.add_exception_handler(Exception, manejar_error_inesperado)
