"""Reportes de incidentes (A4).

Reglas de acceso:
- Cualquier usuario con sesión reporta.
- El ciudadano lista los suyos; voluntario y administrador, los de su organización
  efectiva (la manual prevalece sobre la de la IA); el super admin, todos.
- El detalle lo ven el autor, su organización y el super admin. Un reporte VERIFICADO es
  información pública (sale en el mapa): lo ve cualquiera, pero sin saber quién lo hizo.

Verificación (administrador de la organización efectiva o super admin):
- Solo desde `pendiente`: verificar, rechazar (con motivo opcional) o marcar como duplicado
  de otro reporte. Al rechazar o marcar duplicado se cancelan las asignaciones activas.
- El super admin enruta a mano a una organización (`organizacion_manual_id`) mientras no
  haya IA; no se mueve un reporte cerrado ni uno que ya tomó un voluntario.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.excepciones import Conflicto, DatosInvalidos, NoEncontrado, SinPermiso
from app.integrations import storage_client
from app.jobs import encolar as cola
from app.jobs.eventos.clasificar_reporte_ia import clasificar_reporte_ia
from app.jobs.eventos.notificar_voluntarios_cercanos import notificar_voluntarios_cercanos
from app.middlewares.role_middleware import (
    alcance_organizacion,
    es_super_admin,
    solo_propio,
    verificar_misma_organizacion,
)
from app.models.enums import EstadoReporte, RolUsuario
from app.models.reporte import Reporte
from app.models.usuario import Usuario
from app.repositories import asignaciones_repository, organizaciones_repository
from app.repositories import reportes_repository as repo
from app.schemas.asignaciones_schema import AtencionOut
from app.schemas.reportes_schema import (
    FILTRO_OTROS,
    MAXIMO_ADJUNTOS,
    TIPOS_REPORTE,
    EvidenciaOut,
    ReportanteOut,
    ReporteIn,
    ReporteOut,
    DuplicadoIn,
    RechazoIn,
    ReporteOrganizacionIn,
    ReportePrioridadIn,
    TipoReporteOut,
    etiqueta_tipo,
    normalizar_tipo,
)
from app.utils.geo import punto_desde_latlng
from app.utils.paginacion import Paginacion

CARPETA_EVIDENCIAS = "reportes"
ESTADOS_CERRADOS = (
    EstadoReporte.RECHAZADO,
    EstadoReporte.DUPLICADO,
    EstadoReporte.NO_VERIFICABLE,
    EstadoReporte.ATENDIDO,
)


def organizacion_efectiva(reporte: Reporte) -> UUID | None:
    if reporte.organizacion_manual_id is not None:
        return reporte.organizacion_manual_id
    return reporte.organizacion_objetivo_id


def es_propio(usuario: Usuario, reporte: Reporte) -> bool:
    """Lo creé yo, es de mi organización o soy super admin: veo todo el detalle."""
    return (
        es_super_admin(usuario)
        or reporte.usuario_id == usuario.id
        or (usuario.organizacion_id is not None and organizacion_efectiva(reporte) == usuario.organizacion_id)
    )


def a_salida(usuario: Usuario, reporte: Reporte) -> ReporteOut:
    propio = es_propio(usuario, reporte)
    return ReporteOut(
        id=reporte.id,
        usuario_id=reporte.usuario_id,
        tipo=reporte.tipo,
        tipo_etiqueta=etiqueta_tipo(reporte.tipo),
        descripcion=reporte.descripcion,
        direccion=reporte.direccion,
        ubicacion=reporte.ubicacion,
        estado=reporte.estado,
        prioridad_ia=reporte.prioridad_ia,
        prioridad_manual=reporte.prioridad_manual,
        confianza_ia=reporte.confianza_ia,
        razonamiento_ia=reporte.razonamiento_ia,
        organizacion_objetivo_id=reporte.organizacion_objetivo_id,
        organizacion_manual_id=reporte.organizacion_manual_id,
        verificado_por=reporte.verificado_por,
        verificado_en=reporte.verificado_en,
        motivo_rechazo=reporte.motivo_rechazo,
        duplicado_de_id=reporte.duplicado_de_id,
        evidencias=[
            EvidenciaOut(id=e.id, tipo=e.tipo, url=storage_client.url_publica(e.ruta), mime=e.mime)
            for e in reporte.evidencias
        ],
        reportante=ReportanteOut(id=reporte.autor.id, nombre=reporte.autor.nombre) if propio else None,
        # El ciudadano no recibe quién lo atiende; su organización y el super admin sí
        atencion=(
            AtencionOut.desde_asignacion(reporte.atencion)
            if propio and usuario.rol != RolUsuario.CIUDADANO
            else None
        ),
        creado_en=reporte.creado_en,
        actualizado_en=reporte.actualizado_en,
    )


def listar_tipos() -> list[TipoReporteOut]:
    return [TipoReporteOut(valor=valor, etiqueta=etiqueta) for valor, etiqueta in TIPOS_REPORTE.items()]


def crear(db: Session, usuario: Usuario, datos: ReporteIn, archivos: list[bytes]) -> Reporte:
    if len(archivos) > MAXIMO_ADJUNTOS:
        raise DatosInvalidos(f"Máximo {MAXIMO_ADJUNTOS} fotos o videos por reporte", codigo="DEMASIADOS_ARCHIVOS")
    # Primero se validan todos: si uno no sirve, no se guarda ninguno
    try:
        for contenido in archivos:
            storage_client.validar(contenido)
    except storage_client.ArchivoInvalido as error:
        raise DatosInvalidos(error.detalle, codigo=error.codigo) from None

    reporte = repo.crear(
        db,
        usuario_id=usuario.id,
        tipo=datos.tipo,
        descripcion=datos.descripcion,
        ubicacion=punto_desde_latlng(datos.lat, datos.lng),
        direccion=datos.direccion,
    )
    guardados: list[str] = []
    try:
        for contenido in archivos:
            archivo = storage_client.guardar(contenido, CARPETA_EVIDENCIAS)
            guardados.append(archivo.ruta)
            repo.agregar_evidencia(
                db, reporte, tipo=archivo.clase, ruta=archivo.ruta, mime=archivo.mime, tamano_bytes=archivo.tamano_bytes
            )
        db.commit()
    except Exception:
        # Si la BD falla, no quedan archivos huérfanos en disco
        db.rollback()
        for ruta in guardados:
            storage_client.borrar(ruta)
        raise
    # Después del commit, para que el worker encuentre la fila: la IA sugiere prioridad y organización
    # Al terminar, la clasificación avisa a los voluntarios cercanos de la organización elegida
    cola.encolar(clasificar_reporte_ia, str(reporte.id))
    return reporte


def listar(
    db: Session,
    usuario: Usuario,
    pag: Paginacion,
    *,
    estado: EstadoReporte | None,
    tipo: str | None,
    desde,
    hasta,
) -> tuple[list[Reporte], int]:
    filtros: dict = {"estado": estado, "desde": desde, "hasta": hasta}
    if tipo is not None:
        if tipo.strip().lower() == FILTRO_OTROS:
            filtros["tipos_fuera_de"] = tuple(TIPOS_REPORTE)
        else:
            try:
                filtros["tipo"] = normalizar_tipo(tipo)
            except ValueError as error:
                raise DatosInvalidos(str(error), codigo="TIPO_INVALIDO") from None

    dueno_id = solo_propio(usuario)
    if dueno_id is not None:  # ciudadano
        filtros["usuario_id"] = dueno_id
    else:  # voluntario/administrador → su organización; super_admin → None (todos)
        filtros["organizacion_id"] = alcance_organizacion(usuario)
    return repo.listar(db, pag, **filtros)


def obtener(db: Session, usuario: Usuario, reporte_id: UUID) -> Reporte:
    reporte = repo.obtener_por_id(db, reporte_id)
    if reporte is None:
        raise NoEncontrado("El reporte no existe", codigo="REPORTE_NO_ENCONTRADO")
    if not es_propio(usuario, reporte) and reporte.estado != EstadoReporte.VERIFICADO:
        raise SinPermiso("No tienes acceso a este reporte", codigo="REPORTE_FUERA_DE_ALCANCE")
    return reporte


# --- verificación ---


def _bloquear(db: Session, reporte_id: UUID) -> Reporte:
    reporte = asignaciones_repository.bloquear_reporte(db, reporte_id)
    if reporte is None:
        raise NoEncontrado("El reporte no existe", codigo="REPORTE_NO_ENCONTRADO")
    return reporte


def _para_revisar(db: Session, usuario: Usuario, reporte_id: UUID) -> Reporte:
    reporte = _bloquear(db, reporte_id)
    verificar_misma_organizacion(usuario, organizacion_efectiva(reporte))
    if reporte.estado != EstadoReporte.PENDIENTE:
        raise Conflicto("Solo se revisa un reporte pendiente", codigo="TRANSICION_NO_PERMITIDA")
    return reporte


def _cerrar(db: Session, usuario: Usuario, reporte: Reporte, estado: EstadoReporte, **campos) -> Reporte:
    if estado != EstadoReporte.VERIFICADO:
        asignaciones_repository.cancelar_activas_de_reporte(db, reporte.id)
    reporte = repo.actualizar(
        db, reporte, estado=estado, verificado_por=usuario.id, verificado_en=datetime.now(UTC), **campos
    )
    db.commit()
    return reporte


def verificar(db: Session, usuario: Usuario, reporte_id: UUID) -> Reporte:
    return _cerrar(db, usuario, _para_revisar(db, usuario, reporte_id), EstadoReporte.VERIFICADO)


def rechazar(db: Session, usuario: Usuario, reporte_id: UUID, datos: RechazoIn) -> Reporte:
    reporte = _para_revisar(db, usuario, reporte_id)
    return _cerrar(db, usuario, reporte, EstadoReporte.RECHAZADO, motivo_rechazo=datos.motivo or None)


def marcar_duplicado(db: Session, usuario: Usuario, reporte_id: UUID, datos: DuplicadoIn) -> Reporte:
    reporte = _para_revisar(db, usuario, reporte_id)
    if datos.duplicado_de_id == reporte.id:
        raise DatosInvalidos("Un reporte no puede ser duplicado de sí mismo", codigo="DUPLICADO_DE_SI_MISMO")
    original = repo.obtener_por_id(db, datos.duplicado_de_id)
    if original is None:
        raise NoEncontrado("El reporte original no existe", codigo="REPORTE_ORIGINAL_NO_ENCONTRADO")
    # Si el "original" también era un duplicado, se apunta al primero de la cadena
    if original.estado == EstadoReporte.DUPLICADO and original.duplicado_de_id is not None:
        original = repo.obtener_por_id(db, original.duplicado_de_id) or original
    return _cerrar(db, usuario, reporte, EstadoReporte.DUPLICADO, duplicado_de_id=original.id)


def asignar_organizacion(db: Session, usuario: Usuario, reporte_id: UUID, datos: ReporteOrganizacionIn) -> Reporte:
    """Solo super_admin (se exige en la ruta)."""
    reporte = _bloquear(db, reporte_id)
    organizacion = organizaciones_repository.obtener_por_id(db, datos.organizacion_id)
    if organizacion is None:
        raise NoEncontrado("La organización no existe", codigo="ORGANIZACION_NO_ENCONTRADA")
    if not organizacion.activa:
        raise Conflicto("La organización está desactivada", codigo="ORGANIZACION_INACTIVA")
    if reporte.estado in ESTADOS_CERRADOS:
        raise Conflicto("El reporte ya está cerrado", codigo="REPORTE_CERRADO")
    if asignaciones_repository.contar_activas_de_reporte(db, reporte.id) > 0:
        raise Conflicto(
            "El reporte tiene voluntarios asignados; deben cancelar su asignación antes de moverlo",
            codigo="REPORTE_CON_ASIGNACIONES",
        )
    reporte = repo.actualizar(db, reporte, organizacion_manual_id=organizacion.id)
    db.commit()
    cola.encolar(notificar_voluntarios_cercanos, str(reporte.id))
    return reporte


def fijar_prioridad(db: Session, usuario: Usuario, reporte_id: UUID, datos: ReportePrioridadIn) -> Reporte:
    """Administrador de la organización o super admin. Prevalece sobre la sugerencia de la IA."""
    reporte = _bloquear(db, reporte_id)
    verificar_misma_organizacion(usuario, organizacion_efectiva(reporte))
    reporte = repo.actualizar(db, reporte, prioridad_manual=datos.prioridad_manual)
    db.commit()
    return reporte
