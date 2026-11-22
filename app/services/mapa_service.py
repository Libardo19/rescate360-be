"""Mapa en vivo: une las capas en un solo formato de punto y aplica la privacidad por rol.

Reglas:
- Lo propio (lo creé yo, es de mi organización o soy super admin) sale con la ubicación
  exacta, el detalle y `propio=True`.
- Las solicitudes de otros salen redondeadas a ~200 m y sin descripción: se ve DÓNDE hay
  gente pidiendo ayuda, no QUIÉN ni QUÉ (requisito de ubicación del plan, Ley 1581).
- Los reportes sin verificar solo los ve quien los hizo, su organización y el super admin;
  los verificados son públicos (el filtro está en el repository).
- Las zonas son públicas: todos ven el círculo exacto y el detalle. `propio` solo indica
  si el usuario puede editarlas (administrador de su organización o super admin).
- Polling: el cliente manda `desde` con el `generado_en` de la respuesta anterior y recibe
  solo lo que cambió, incluido lo que se cerró (`activo=False`) para quitarlo del mapa.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.excepciones import DatosInvalidos
from app.middlewares.role_middleware import es_super_admin
from app.models.alerta import Alerta
from app.models.evento_sismico import EventoSismico
from app.models.enums import EstadoAlerta, RolUsuario
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.models.usuario import Usuario
from app.models.zona_peligrosa import ZonaPeligrosa
from app.repositories import mapa_repository as repo
from app.repositories import sismos_repository
from app.schemas.mapa_schema import CAPAS_MAPA, MapaOut, PuntoMapa
from app.schemas.reportes_schema import etiqueta_tipo
from app.services import alertas_service, reportes_service, sismos_service, zonas_peligrosas_service
from app.services.solicitudes_ayuda_service import organizacion_efectiva
from app.utils.geo import latlng_desde_punto

# Grilla de redondeo para lo ajeno: 0.002° ≈ 220 m en Colombia
GRILLA_GRADOS = 0.002
# Margen para no perder cambios que se confirmaron justo mientras se armaba la respuesta
# anterior. Un punto repetido no hace daño: el cliente reemplaza por id.
MARGEN_POLLING = timedelta(seconds=5)
RADIO_MAXIMO_M = 50_000
LARGO_DETALLE = 140

ETIQUETAS_SOLICITUD = {
    "medica": "Ayuda médica",
    "alimentaria": "Alimentos",
    "refugio": "Refugio",
    "rescate": "Rescate",
    "ropa": "Ropa",
    "otro": "Otra ayuda",
}


def _redondear(valor: float) -> float:
    return round(round(valor / GRILLA_GRADOS) * GRILLA_GRADOS, 6)


def _corto(texto: str) -> str:
    return texto if len(texto) <= LARGO_DETALLE else texto[: LARGO_DETALLE - 1].rstrip() + "…"


def leer_capas(capas: str) -> set[str]:
    pedidas = {c.strip() for c in capas.split(",") if c.strip()}
    desconocidas = pedidas - set(CAPAS_MAPA)
    if not pedidas or desconocidas:
        raise DatosInvalidos(
            f"Capas válidas: {', '.join(CAPAS_MAPA)}", codigo="CAPA_INVALIDA"
        )
    return pedidas


def _punto_solicitud(usuario: Usuario, solicitud: SolicitudAyuda) -> PuntoMapa:
    propio = (
        es_super_admin(usuario)
        or solicitud.usuario_id == usuario.id
        or (usuario.organizacion_id is not None and organizacion_efectiva(solicitud) == usuario.organizacion_id)
    )
    posicion = latlng_desde_punto(solicitud.ubicacion)
    titulo = ETIQUETAS_SOLICITUD.get(solicitud.tipo.value, "Solicitud de ayuda")
    if solicitud.origen.value == "sos":
        titulo = "SOS"
    prioridad = solicitud.prioridad_manual or solicitud.prioridad_ia
    return PuntoMapa(
        id=solicitud.id,
        capa="solicitud",
        tipo=solicitud.tipo.value,
        titulo=titulo,
        detalle=_corto(solicitud.descripcion) if propio else "Solicitud de ayuda en la zona (ubicación aproximada)",
        estado=solicitud.estado.value,
        prioridad=prioridad.value,
        lat=posicion["lat"] if propio else _redondear(posicion["lat"]),
        lng=posicion["lng"] if propio else _redondear(posicion["lng"]),
        aproximada=not propio,
        propio=propio,
        activo=solicitud.estado in repo.SOLICITUDES_ABIERTAS,
        actualizado_en=solicitud.actualizado_en,
    )


def _punto_reporte(usuario: Usuario, reporte: Reporte) -> PuntoMapa:
    propio = reportes_service.es_propio(usuario, reporte)
    posicion = latlng_desde_punto(reporte.ubicacion)
    # Un reporte verificado es información pública: va con su ubicación exacta
    return PuntoMapa(
        id=reporte.id,
        capa="reporte",
        tipo=reporte.tipo,
        titulo=etiqueta_tipo(reporte.tipo),
        detalle=_corto(reporte.descripcion),
        estado=reporte.estado.value,
        prioridad=(reporte.prioridad_manual or reporte.prioridad_ia).value,
        lat=posicion["lat"],
        lng=posicion["lng"],
        aproximada=False,
        propio=propio,
        activo=reporte.estado in repo.REPORTES_ABIERTOS,
        actualizado_en=reporte.actualizado_en,
    )


def _punto_zona(usuario: Usuario, zona: ZonaPeligrosa) -> PuntoMapa:
    posicion = latlng_desde_punto(zona.centro)
    return PuntoMapa(
        id=zona.id,
        capa="zona",
        tipo=zona.tipo_riesgo,
        titulo=zona.nombre,
        detalle=_corto(zona.descripcion or "Zona de riesgo"),
        estado=zona.estado.value,
        prioridad=zona.nivel.value,
        lat=posicion["lat"],
        lng=posicion["lng"],
        radio_m=zona.radio_m,
        # Las zonas son información pública: el círculo exacto se muestra a todos
        aproximada=False,
        propio=zonas_peligrosas_service.es_propia(usuario, zona),
        activo=zona.estado in repo.ZONAS_VIGENTES,
        actualizado_en=zona.actualizado_en,
    )


def _punto_alerta(usuario: Usuario, alerta: Alerta) -> PuntoMapa:
    posicion = latlng_desde_punto(alerta.centro)
    return PuntoMapa(
        id=alerta.id,
        capa="alerta",
        tipo=alerta.tipo,
        titulo=alerta.titulo,
        detalle=_corto(alerta.mensaje),
        estado=alerta.estado.value,
        prioridad=alerta.nivel.value,
        lat=posicion["lat"],
        lng=posicion["lng"],
        radio_m=alerta.radio_m,
        # Las alertas son información pública: el círculo exacto se muestra a todos
        aproximada=False,
        propio=alertas_service.es_propia(usuario, alerta),
        activo=alerta.estado == EstadoAlerta.ACTIVA,
        actualizado_en=alerta.actualizado_en,
    )


# Los sismos se muestran durante 24 horas. Al ser de todo el mundo, la capa tiene un tope más alto
# (unos 300-400 al día con magnitud >= 0) y no se recorta por la posición de quien consulta.
VIGENCIA_SISMO = timedelta(hours=24)
MAXIMO_SISMOS = 1500


def _punto_sismo(evento: EventoSismico) -> PuntoMapa:
    posicion = latlng_desde_punto(evento.epicentro)
    local = sismos_service.es_local(evento)
    return PuntoMapa(
        id=evento.id,
        capa="sismo",
        tipo="sismo",
        titulo=f"Sismo M{evento.magnitud:.1f}",
        detalle=_corto(evento.lugar),
        estado="colombia" if local else "mundo",
        prioridad=None,
        lat=posicion["lat"],
        lng=posicion["lng"],
        # El radio de afectación solo tiene sentido en Colombia (donde se alerta)
        radio_m=evento.radio_afectacion_m if local else None,
        magnitud=evento.magnitud,
        aproximada=False,
        propio=False,
        activo=True,
        actualizado_en=evento.creado_en,
    )


def obtener_mapa(
    db: Session,
    usuario: Usuario,
    *,
    lat: float | None,
    lng: float | None,
    radio_m: float,
    capas: str,
    desde: datetime | None,
) -> MapaOut:
    pedidas = leer_capas(capas)
    if (lat is None) != (lng is None):
        raise DatosInvalidos("Envía lat y lng juntos, o ninguno", codigo="UBICACION_INCOMPLETA")
    centro = (lat, lng) if lat is not None else None
    radio_m = min(radio_m, RADIO_MAXIMO_M)
    # Hora de la BD, no la del servidor: es la misma que usa actualizado_en
    generado_en = db.scalar(select(func.now()))
    filtro_desde = desde - MARGEN_POLLING if desde is not None else None

    puntos: list[PuntoMapa] = []
    if "solicitudes" in pedidas:
        solicitudes = repo.listar_solicitudes(db, centro=centro, radio_m=radio_m, desde=filtro_desde)
        puntos += [_punto_solicitud(usuario, s) for s in solicitudes]
    if "reportes" in pedidas:
        reportes = repo.listar_reportes(
            db,
            centro=centro,
            radio_m=radio_m,
            desde=filtro_desde,
            usuario_id=usuario.id,
            organizacion_id=usuario.organizacion_id if usuario.rol != RolUsuario.CIUDADANO else None,
            todos=es_super_admin(usuario),
        )
        puntos += [_punto_reporte(usuario, r) for r in reportes]
    if "zonas" in pedidas:
        zonas = repo.listar_zonas(db, centro=centro, radio_m=radio_m, desde=filtro_desde)
        puntos += [_punto_zona(usuario, z) for z in zonas]
    if "alertas" in pedidas:
        alertas = repo.listar_alertas(db, centro=centro, radio_m=radio_m, desde=filtro_desde)
        puntos += [_punto_alerta(usuario, a) for a in alertas]
    if "sismos" in pedidas:
        sismos = sismos_repository.recientes_para_mapa(
            db,
            ocurrido_desde=generado_en - VIGENCIA_SISMO,
            registrado_desde=filtro_desde,
            limite=MAXIMO_SISMOS,
        )
        puntos += [_punto_sismo(e) for e in sismos]
    # centros: se suma cuando el mapa los necesite (B4 ya tiene su propio GET /centros-ayuda)
    return MapaOut(puntos=puntos, generado_en=generado_en)
