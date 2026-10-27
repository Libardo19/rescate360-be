"""Logging con un id por petición.

Cada respuesta lleva el header `X-Request-ID` (o reutiliza el que mande el cliente),
y cada línea de log de esa petición lo incluye. Sirve para seguir un error reportado
por Oscar o Elkin hasta la línea exacta del log.
"""

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_actual: ContextVar[str] = ContextVar("request_id", default="-")


class _FiltroRequestId(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_actual.get()
        return True


def configurar_logging(nivel: str = "INFO") -> None:
    manejador = logging.StreamHandler()
    manejador.addFilter(_FiltroRequestId())
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(nivel)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_actual.set(request_id)
        try:
            respuesta = await call_next(request)
        finally:
            request_id_actual.reset(token)
        respuesta.headers["X-Request-ID"] = request_id
        return respuesta
