"""HTTP de personas desaparecidas: arma la respuesta y llama al service. Sin SQL ni reglas."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.enums import EstadoCasoPersona
from app.models.usuario import Usuario
from app.schemas.personas_desaparecidas_schema import (
    EstadoPersonaIn,
    PersonaEdicionIn,
    PersonaIn,
    PersonaOut,
    Sexo,
)
from app.services import personas_desaparecidas_service as service
from app.utils.paginacion import Pagina, Paginacion, paginacion


def crear_persona(
    request: Request,
    nombre: Annotated[str, Form()],
    edad: Annotated[int, Form()],
    sexo: Annotated[Sexo, Form()],
    fecha_vista: Annotated[date, Form(description="AAAA-MM-DD")],
    lugar: Annotated[str, Form(description="Dónde se vio por última vez")],
    descripcion: Annotated[str, Form()],
    contacto_nombre: Annotated[str, Form()],
    contacto_telefono: Annotated[str, Form(description="E.164 o celular colombiano de 10 dígitos")],
    estatura: Annotated[str | None, Form()] = None,
    senas_particulares: Annotated[str | None, Form()] = None,
    vestimenta: Annotated[str | None, Form()] = None,
    lat: Annotated[float | None, Form()] = None,
    lng: Annotated[float | None, Form()] = None,
    acepta_publicar_foto: Annotated[bool, Form()] = False,
    foto: Annotated[UploadFile | None, File(description="Foto reciente del rostro (JPG, PNG o WEBP)")] = None,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonaOut:
    # Igual que en reportes: los campos del formulario se validan con el schema y devuelven
    # el mismo 422 de siempre
    try:
        datos = PersonaIn(
            nombre=nombre,
            edad=edad,
            sexo=sexo,
            estatura=estatura,
            fecha_vista=fecha_vista,
            lugar=lugar,
            descripcion=descripcion,
            senas_particulares=senas_particulares,
            vestimenta=vestimenta,
            contacto_nombre=contacto_nombre,
            contacto_telefono=contacto_telefono,
            lat=lat,
            lng=lng,
            acepta_publicar_foto=acepta_publicar_foto,
        )
    except ValidationError as error:
        raise RequestValidationError(
            [{**e, "loc": ("body", *e["loc"])} for e in error.errors(include_url=False)]
        ) from None
    contenido = None
    if foto is not None:
        contenido = foto.file.read(get_settings().foto_max_mb * 1024 * 1024 + 1)
    ip = request.client.host if request.client else None
    persona = service.crear(db, usuario, datos, contenido, ip)
    return service.a_salida(usuario, persona, detalle=True)


def listar_personas(
    q: str | None = None,
    estado: EstadoCasoPersona | None = None,
    solo_mias: bool = False,
    pag: Paginacion = Depends(paginacion),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Pagina[PersonaOut]:
    items, total = service.listar(db, pag, usuario, q=q, estado=estado, solo_mias=solo_mias)
    return Pagina.crear([service.a_salida(usuario, p) for p in items], total, pag)


def obtener_persona(
    persona_id: UUID, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> PersonaOut:
    return service.a_salida(usuario, service.obtener(db, persona_id), detalle=True)


def editar_persona(
    persona_id: UUID,
    datos: PersonaEdicionIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonaOut:
    return service.a_salida(usuario, service.editar(db, usuario, persona_id, datos), detalle=True)


def cambiar_estado(
    persona_id: UUID,
    datos: EstadoPersonaIn,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PersonaOut:
    return service.a_salida(usuario, service.cambiar_estado(db, usuario, persona_id, datos), detalle=True)
