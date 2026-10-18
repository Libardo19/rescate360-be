"""Excepciones de negocio.

Los services lanzan estas excepciones y `error_handler_middleware` las convierte
en la respuesta del contrato: `{"detalle": "...", "codigo": "..."}`.

Convención de códigos: MAYÚSCULAS con el prefijo del módulo, por ejemplo
`REPORTE_NO_ENCONTRADO` o `EMAIL_YA_REGISTRADO`. Si no se pasa un código, se usa
el genérico de la clase.

    raise NoEncontrado("El reporte no existe", codigo="REPORTE_NO_ENCONTRADO")
"""


class ErrorNegocio(Exception):
    status_code = 400
    codigo_por_defecto = "ERROR"

    def __init__(self, detalle: str, codigo: str | None = None):
        super().__init__(detalle)
        self.detalle = detalle
        self.codigo = codigo or self.codigo_por_defecto


class NoAutenticado(ErrorNegocio):
    """Falta el token, es inválido o expiró (401)."""

    status_code = 401
    codigo_por_defecto = "NO_AUTENTICADO"


class SinPermiso(ErrorNegocio):
    """El usuario está autenticado pero su rol o alcance no le permite la acción (403)."""

    status_code = 403
    codigo_por_defecto = "SIN_PERMISO"


class NoEncontrado(ErrorNegocio):
    status_code = 404
    codigo_por_defecto = "NO_ENCONTRADO"


class Conflicto(ErrorNegocio):
    """Choca con el estado actual: duplicado, transición de estado no permitida, etc. (409)."""

    status_code = 409
    codigo_por_defecto = "CONFLICTO"


class DatosInvalidos(ErrorNegocio):
    """Regla de negocio sobre los datos que Pydantic no puede validar solo (422)."""

    status_code = 422
    codigo_por_defecto = "DATOS_INVALIDOS"
