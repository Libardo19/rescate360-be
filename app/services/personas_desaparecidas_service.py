"""Personas desaparecidas (A5).

Reglas de acceso:
- Cualquier usuario con sesión reporta una persona y ve el listado y el detalle: difundir
  la ficha es lo que ayuda a encontrarla.
- Editar la ficha y cambiar el estado: quien la reportó, un administrador o el super admin.

Reglas legales:
- Si es menor de edad (`es_menor`), la foto solo la ven quien la reportó y los
  administradores (Ley 1098 de 2006, Código de Infancia y Adolescencia).
- El teléfono de la familia nunca sale en el listado, solo en el detalle.
- Publicar una foto exige la autorización `foto_persona`, que queda en `consentimientos`.
- El detalle trae el aviso legal (no esperar 72 horas, Mecanismo de Búsqueda Urgente).
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.excepciones import DatosInvalidos, NoEncontrado, SinPermiso
from app.integrations import storage_client
from app.jobs import encolar as cola
from app.jobs.eventos.notificar_persona_encontrada import notificar_persona_encontrada
from app.middlewares.role_middleware import ROLES_ADMIN
from app.models.enums import EstadoCasoPersona, TipoConsentimiento
from app.models.persona_desaparecida import PersonaDesaparecida
from app.models.usuario import Usuario
from app.repositories import consentimientos_repository
from app.repositories import personas_desaparecidas_repository as repo
from app.schemas.personas_desaparecidas_schema import (
    AVISO_LEGAL,
    EDAD_MAYORIA,
    EstadoPersonaIn,
    PersonaEdicionIn,
    PersonaIn,
    PersonaOut,
)
from app.utils.geo import punto_desde_latlng
from app.utils.paginacion import Paginacion

CARPETA_FOTOS = "personas"


def es_mia(usuario: Usuario, persona: PersonaDesaparecida) -> bool:
    return persona.reportado_por == usuario.id


def puede_gestionar(usuario: Usuario, persona: PersonaDesaparecida) -> bool:
    return es_mia(usuario, persona) or usuario.rol in ROLES_ADMIN


def a_salida(usuario: Usuario, persona: PersonaDesaparecida, *, detalle: bool = False) -> PersonaOut:
    gestiona = puede_gestionar(usuario, persona)
    foto_oculta = persona.foto_ruta is not None and persona.es_menor and not gestiona
    return PersonaOut(
        id=persona.id,
        nombre=persona.nombre,
        edad=persona.edad,
        sexo=persona.sexo,
        estatura=persona.estatura,
        fecha_vista=persona.fecha_vista,
        lugar=persona.lugar,
        descripcion=persona.descripcion,
        senas_particulares=persona.senas_particulares,
        vestimenta=persona.vestimenta,
        estado=persona.estado_caso,
        es_menor=persona.es_menor,
        foto_url=None if foto_oculta or persona.foto_ruta is None else storage_client.url_publica(persona.foto_ruta),
        foto_oculta=foto_oculta,
        ubicacion=persona.ultima_ubicacion,
        contacto_nombre=persona.contacto_nombre if detalle else None,
        contacto_telefono=persona.contacto_telefono if detalle else None,
        es_mia=es_mia(usuario, persona),
        puede_gestionar=gestiona,
        aviso=AVISO_LEGAL if detalle else None,
        encontrado_en=persona.encontrado_en,
        creado_en=persona.creado_en,
        actualizado_en=persona.actualizado_en,
    )


def crear(
    db: Session, usuario: Usuario, datos: PersonaIn, foto: bytes | None, ip: str | None
) -> PersonaDesaparecida:
    if foto is not None:
        if not datos.acepta_publicar_foto:
            raise DatosInvalidos(
                "Para publicar la foto debes autorizarlo (acepta_publicar_foto)", codigo="FOTO_SIN_AUTORIZACION"
            )
        try:
            if storage_client.validar(foto).clase != "foto":
                raise DatosInvalidos("Solo se acepta una foto JPG, PNG o WEBP", codigo="ARCHIVO_NO_PERMITIDO")
        except storage_client.ArchivoInvalido as error:
            raise DatosInvalidos(error.detalle, codigo=error.codigo) from None

    ubicacion = punto_desde_latlng(datos.lat, datos.lng) if datos.lat is not None else None
    persona = repo.crear(
        db,
        reportado_por=usuario.id,
        nombre=datos.nombre,
        edad=datos.edad,
        sexo=datos.sexo,
        estatura=datos.estatura,
        fecha_vista=datos.fecha_vista,
        lugar=datos.lugar,
        descripcion=datos.descripcion,
        senas_particulares=datos.senas_particulares,
        vestimenta=datos.vestimenta,
        contacto_nombre=datos.contacto_nombre,
        contacto_telefono=datos.contacto_telefono,
        es_menor=datos.edad < EDAD_MAYORIA,
        ultima_ubicacion=ubicacion,
    )
    ruta: str | None = None
    try:
        if foto is not None:
            consentimientos_repository.registrar(
                db,
                usuario.id,
                TipoConsentimiento.FOTO_PERSONA,
                aceptado=True,
                version_politica=get_settings().version_politica_datos,
                ip=ip,
            )
            ruta = storage_client.guardar(foto, CARPETA_FOTOS).ruta
            persona.foto_ruta = ruta
            db.flush()
        db.commit()
    except Exception:
        db.rollback()
        if ruta is not None:
            storage_client.borrar(ruta)
        raise
    return persona


def listar(
    db: Session,
    pag: Paginacion,
    usuario: Usuario,
    *,
    q: str | None,
    estado: EstadoCasoPersona | None,
    solo_mias: bool,
) -> tuple[list[PersonaDesaparecida], int]:
    return repo.listar(
        db, pag, q=(q or "").strip() or None, estado=estado, reportado_por=usuario.id if solo_mias else None
    )


def obtener(db: Session, persona_id: UUID) -> PersonaDesaparecida:
    persona = repo.obtener_por_id(db, persona_id)
    if persona is None:
        raise NoEncontrado("La persona no existe", codigo="PERSONA_NO_ENCONTRADA")
    return persona


def _para_gestionar(db: Session, usuario: Usuario, persona_id: UUID) -> PersonaDesaparecida:
    persona = repo.bloquear(db, persona_id)
    if persona is None:
        raise NoEncontrado("La persona no existe", codigo="PERSONA_NO_ENCONTRADA")
    if not puede_gestionar(usuario, persona):
        raise SinPermiso(
            "Solo quien la reportó o un administrador puede cambiar esta ficha", codigo="PERSONA_FUERA_DE_ALCANCE"
        )
    return persona


def editar(db: Session, usuario: Usuario, persona_id: UUID, datos: PersonaEdicionIn) -> PersonaDesaparecida:
    persona = _para_gestionar(db, usuario, persona_id)
    campos = datos.model_dump(exclude_unset=True)
    for obligatorio in ("nombre", "edad", "sexo", "fecha_vista", "lugar", "descripcion", "contacto_nombre", "contacto_telefono"):
        if obligatorio in campos and campos[obligatorio] is None:
            raise DatosInvalidos(f"El campo {obligatorio} no se puede borrar", codigo="CAMPO_OBLIGATORIO")
    if "ubicacion" in campos:
        ubicacion = campos.pop("ubicacion")
        campos["ultima_ubicacion"] = (
            punto_desde_latlng(ubicacion["lat"], ubicacion["lng"]) if ubicacion is not None else None
        )
    if campos.get("edad") is not None:
        campos["es_menor"] = campos["edad"] < EDAD_MAYORIA
    persona = repo.actualizar(db, persona, **campos)
    db.commit()
    return persona


def cambiar_estado(db: Session, usuario: Usuario, persona_id: UUID, datos: EstadoPersonaIn) -> PersonaDesaparecida:
    persona = _para_gestionar(db, usuario, persona_id)
    if persona.estado_caso == datos.estado:
        return persona
    encontrada = datos.estado == EstadoCasoPersona.ENCONTRADO
    persona = repo.actualizar(
        db, persona, estado_caso=datos.estado, encontrado_en=datetime.now(UTC) if encontrada else None
    )
    db.commit()
    if encontrada:
        cola.encolar(notificar_persona_encontrada, str(persona.id))
    return persona
