"""Sismos (B8).

- Cada minuto el job `sincronizar_sismos` lee el feed del USGS y registra los sismos de
  Colombia (idempotente por `id_externo`).
- Desde la magnitud SISMOS_MAGNITUD_ALERTA (4.5): se publica una alerta del sistema sobre el
  epicentro y se abre un "¿Estás bien?" a quien tenga su ubicación reciente dentro del radio.
- El radio crece con la magnitud: 10 km para un 4.5 y se duplica por cada punto (tope 300 km).
- `POST /sismos/simular` (solo super admin y solo en local) crea uno falso para la demo.
- Todo se presenta como información de fuentes públicas, no como alerta temprana oficial.
"""

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.excepciones import NoEncontrado, SinPermiso
from app.integrations.sismos_client import SismoFeed
from app.models.enums import NivelAlerta
from app.models.evento_sismico import EventoSismico
from app.models.usuario import Usuario
from app.repositories import check_ins_repository, sismos_repository as repo
from app.schemas.sismos_schema import SismoOut, SismoSimuladoIn
from app.services import alertas_service
from app.utils.geo import latlng_desde_punto
from app.utils.paginacion import Paginacion

RADIO_BASE_M = 10_000
RADIO_MAXIMO_M = 300_000
HORAS_ALERTA = 6
HORAS_UBICACION = 24


def radio_afectacion(magnitud: float) -> float:
    return float(min(RADIO_BASE_M * 2 ** (magnitud - 4.5), RADIO_MAXIMO_M))


def nivel_por_magnitud(magnitud: float) -> NivelAlerta:
    if magnitud >= 6:
        return NivelAlerta.ALTO
    if magnitud >= 5:
        return NivelAlerta.MEDIO
    return NivelAlerta.BAJO


def a_salida(db: Session, usuario: Usuario | None, evento: EventoSismico) -> SismoOut:
    salida = SismoOut.model_validate(evento)
    if usuario is not None and usuario.ubicacion_actual is not None:
        posicion = latlng_desde_punto(usuario.ubicacion_actual)
        salida.distancia_m = round(repo.distancia_a(db, evento, posicion["lat"], posicion["lng"]), 1)
    return salida


def registrar(db: Session, sismo: SismoFeed, fuente: str = "usgs") -> tuple[EventoSismico, bool]:
    evento, nuevo = repo.registrar(
        db,
        id_externo=sismo.id_externo,
        fuente=fuente,
        magnitud=sismo.magnitud,
        profundidad_km=sismo.profundidad_km,
        lugar=sismo.lugar,
        lat=sismo.lat,
        lng=sismo.lng,
        ocurrido_en=sismo.ocurrido_en,
        radio_afectacion_m=radio_afectacion(sismo.magnitud),
    )
    db.commit()
    return evento, nuevo


def atender_si_es_fuerte(db: Session, evento: EventoSismico) -> bool:
    """Publica la alerta y abre los check-ins una sola vez por sismo. Devuelve si lo atendió."""
    if evento.magnitud < get_settings().sismos_magnitud_alerta or evento.alerta_id is not None:
        return False
    epicentro = latlng_desde_punto(evento.epicentro)
    alerta = alertas_service.publicar(
        db,
        creado_por=None,  # la crea el sistema
        organizacion_id=None,
        titulo=f"Sismo de magnitud {evento.magnitud:.1f}",
        tipo="sismo",
        mensaje=(
            f"{evento.lugar}. Si estás en la zona, revisa si hay heridos y daños, aléjate de estructuras "
            "afectadas y responde en la app si estás bien."
        ),
        nivel=nivel_por_magnitud(evento.magnitud),
        lat=epicentro["lat"],
        lng=epicentro["lng"],
        radio_m=evento.radio_afectacion_m,
        horas_vigencia=HORAS_ALERTA,
        origen="sismo",
    )
    evento.alerta_id = alerta.id
    db.flush()
    check_ins_repository.abrir_para_usuarios_en_circulo(
        db,
        evento_sismico_id=evento.id,
        zona=alerta.zona_afectada,
        horas_ubicacion=HORAS_UBICACION,
        vence_en=datetime.now(UTC) + timedelta(minutes=get_settings().check_in_minutos),
    )
    db.commit()
    return True


def simular(db: Session, usuario: Usuario, datos: SismoSimuladoIn) -> EventoSismico:
    if get_settings().app_env != "local":
        raise SinPermiso("El simulacro solo está disponible en el entorno local", codigo="SIMULACRO_NO_DISPONIBLE")
    sismo = SismoFeed(
        id_externo=f"simulado:{uuid.uuid4().hex}",
        magnitud=datos.magnitud,
        profundidad_km=datos.profundidad_km,
        lugar=datos.lugar,
        lat=datos.lat,
        lng=datos.lng,
        ocurrido_en=datetime.now(UTC),
    )
    evento, _ = registrar(db, sismo, fuente="simulado")
    atender_si_es_fuerte(db, evento)
    db.refresh(evento)
    return evento


def listar(
    db: Session, pag: Paginacion, *, desde: datetime | None, magnitud_min: float | None
) -> tuple[list[EventoSismico], int]:
    return repo.listar(db, pag, desde=desde, magnitud_min=magnitud_min)


def obtener(db: Session, evento_id: UUID) -> EventoSismico:
    evento = repo.obtener_por_id(db, evento_id)
    if evento is None:
        raise NoEncontrado("El sismo no existe", codigo="SISMO_NO_ENCONTRADO")
    return evento
