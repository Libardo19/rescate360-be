"""HTTP de reportes: arma la respuesta y llama al service. Sin SQL ni reglas."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import EstadoReporte
from app.models.usuario import Usuario
from app.schemas.reportes_schema import (
    DuplicadoIn,
    RechazoIn,
    ReporteIn,
    ReporteOrganizacionIn,
    ReporteOut,
    ReportePrioridadIn,
    TipoReporteOut,
)
from app.services import reportes_service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def _leer(archivo: UploadFile) -> bytes:
    # Se lee como máximo el límite más grande + 1 byte: si se pasa, el storage lo rechaza
    # sin cargar en memoria un archivo gigante
    limite = max(get_settings().foto_max_mb, get_settings().video_max_mb) * 1024 * 1024
    return archivo.file.read(limite + 1)


def listar_tipos() -> list[TipoReporteOut]:
    return reportes_service.listar_tipos()


def crear_reporte(
    tipo: Annotated[str, Form(description="De GET /reportes/tipos o uno escrito por el usuario")],
    descripcion: Annotated[str, Form()],
    lat: Annotated[float, Form()],
    lng: Annotated[float, Form()],
    direccion: Annotated[str | None, Form()] = None,
    archivos: Annotated[list[UploadFile], File(description="Fotos (JPG, PNG, WEBP) y videos (MP4, MOV)")] = [],
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReporteOut:
    # FastAPI no mezcla un modelo de formulario con archivos en la misma ruta: los campos
    # llegan sueltos y se validan con ReporteIn, devolviendo el mismo 422 de siempre
    try:
        datos = ReporteIn(tipo=tipo, descripcion=descripcion, lat=lat, lng=lng, direccion=direccion)
    except ValidationError as error:
        raise RequestValidationError(
            [{**e, "loc": ("body", *e["loc"])} for e in error.errors(include_url=False)]
        ) from None
    reporte = reportes_service.crear(db, usuario, datos, [_leer(a) for a in archivos])
    return reportes_service.a_salida(usuario, reporte)


def listar_reportes(
    estado: EstadoReporte | None = None,
    tipo: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[ReporteOut]:
    items, total = reportes_service.listar(db, usuario, pag, estado=estado, tipo=tipo, desde=desde, hasta=hasta)
    return Pagina.crear([reportes_service.a_salida(usuario, r) for r in items], total, pag)


def obtener_reporte(
    reporte_id: UUID,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReporteOut:
    return reportes_service.a_salida(usuario, reportes_service.obtener(db, usuario, reporte_id))


def verificar_reporte(
    reporte_id: UUID, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> ReporteOut:
    return reportes_service.a_salida(usuario, reportes_service.verificar(db, usuario, reporte_id))


def rechazar_reporte(
    reporte_id: UUID,
    datos: RechazoIn | None = None,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReporteOut:
    reporte = reportes_service.rechazar(db, usuario, reporte_id, datos or RechazoIn())
    return reportes_service.a_salida(usuario, reporte)


def marcar_duplicado(
    reporte_id: UUID,
    datos: DuplicadoIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReporteOut:
    return reportes_service.a_salida(usuario, reportes_service.marcar_duplicado(db, usuario, reporte_id, datos))


def asignar_organizacion(
    reporte_id: UUID,
    datos: ReporteOrganizacionIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReporteOut:
    return reportes_service.a_salida(usuario, reportes_service.asignar_organizacion(db, usuario, reporte_id, datos))


def fijar_prioridad(
    reporte_id: UUID,
    datos: ReportePrioridadIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReporteOut:
    return reportes_service.a_salida(usuario, reportes_service.fijar_prioridad(db, usuario, reporte_id, datos))
