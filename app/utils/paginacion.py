"""Paginación común a todos los listados.

Entrada `?pagina=1&por_pagina=20` y salida `{items, total, pagina, por_pagina}`.

Uso en un controller:

    def listar(pag: Paginacion = Depends(paginacion), db: Session = Depends(get_db)) -> Pagina[ReporteOut]:
        items, total = reportes_service.listar(db, pag)
        return Pagina.crear(items, total, pag)

Y en el repository: `.offset(pag.offset).limit(pag.por_pagina)`.
"""

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

POR_PAGINA_DEFECTO = 20
POR_PAGINA_MAXIMO = 100

T = TypeVar("T")


class Paginacion(BaseModel):
    pagina: int = Field(1, ge=1)
    por_pagina: int = Field(POR_PAGINA_DEFECTO, ge=1, le=POR_PAGINA_MAXIMO)

    @property
    def offset(self) -> int:
        return (self.pagina - 1) * self.por_pagina


def paginacion(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(POR_PAGINA_DEFECTO, ge=1, le=POR_PAGINA_MAXIMO),
) -> Paginacion:
    """Dependencia de FastAPI que lee la paginación del query string."""
    return Paginacion(pagina=pagina, por_pagina=por_pagina)


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    pagina: int
    por_pagina: int

    @classmethod
    def crear(cls, items: list, total: int, pag: Paginacion) -> "Pagina[T]":
        return cls(items=items, total=total, pagina=pag.pagina, por_pagina=pag.por_pagina)
