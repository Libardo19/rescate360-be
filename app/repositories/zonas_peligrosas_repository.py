from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, null, or_, select
from sqlalchemy.orm import Session

from app.models.enums import EstadoZona, NivelZona
from app.models.organizacion import Organizacion
from app.models.zona_peligrosa import ZonaPeligrosa
from app.utils.geo import cerca_de, circulo_a_poligono, distancia_m, punto_desde_latlng
from app.utils.paginacion import Paginacion

# Lo único que una modificación puede tocar (defensa en profundidad: nada de **campos libres)
CAMPOS_EDITABLES = {"nombre", "tipo_riesgo", "nivel", "descripcion", "estado"}


def existe_organizacion(db: Session, organizacion_id: UUID) -> bool:
    return db.get(Organizacion, organizacion_id) is not None


def crear(
    db: Session,
    *,
    nombre: str,
    tipo_riesgo: str,
    nivel: NivelZona,
    descripcion: str | None,
    estado: EstadoZona,
    lat: float,
    lng: float,
    radio_m: float,
    gestionado_por: UUID,
    organizacion_id: UUID | None,
) -> ZonaPeligrosa:
    zona = ZonaPeligrosa(
        nombre=nombre,
        tipo_riesgo=tipo_riesgo,
        nivel=nivel,
        descripcion=descripcion,
        estado=estado,
        centro=punto_desde_latlng(lat, lng),
        radio_m=radio_m,
        # Expresión SQL: PostGIS calcula el polígono en metros reales (ver utils/geo.py)
        area=circulo_a_poligono(lat, lng, radio_m),
        gestionado_por=gestionado_por,
        organizacion_id=organizacion_id,
    )
    db.add(zona)
    db.flush()
    db.refresh(zona)  # carga el polígono calculado y los valores por defecto del servidor
    return zona


def obtener_por_id(db: Session, zona_id: UUID) -> ZonaPeligrosa | None:
    return db.get(ZonaPeligrosa, zona_id)


def listar(
    db: Session,
    pag: Paginacion,
    *,
    estados: Sequence[EstadoZona],
    organizacion_visible: UUID | None = None,
    centro: tuple[float, float] | None = None,
    radio_m: float = 5000,
) -> tuple[list[tuple[ZonaPeligrosa, float | None]], int]:
    """Zonas en alguno de `estados`. Devuelve (zona, distancia en metros al CENTRO o None).

    organizacion_visible: si viene, las de esa organización MÁS las globales (sin organización).
    centro: si viene, solo las zonas cuyo círculo queda a `radio_m` o menos, ordenadas por cercanía.
    """
    if not estados:
        return [], 0

    filtros = [ZonaPeligrosa.estado.in_(list(estados))]
    if organizacion_visible is not None:
        filtros.append(
            or_(ZonaPeligrosa.organizacion_id == organizacion_visible, ZonaPeligrosa.organizacion_id.is_(None))
        )

    if centro is not None:
        filtros.append(cerca_de(ZonaPeligrosa.area, centro[0], centro[1], radio_m))
        distancia = distancia_m(ZonaPeligrosa.centro, centro[0], centro[1])
        orden = (distancia.asc(), ZonaPeligrosa.id)
        columna_distancia = distancia.label("distancia_centro")
    else:
        orden = (ZonaPeligrosa.actualizado_en.desc(), ZonaPeligrosa.id)
        columna_distancia = null().label("distancia_centro")

    total = db.scalar(select(func.count()).select_from(ZonaPeligrosa).where(*filtros)) or 0
    consulta = (
        select(ZonaPeligrosa, columna_distancia)
        .where(*filtros)
        .order_by(*orden)
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    filas = db.execute(consulta).all()
    return [(fila.ZonaPeligrosa, fila.distancia_centro) for fila in filas], total


def actualizar(
    db: Session,
    zona: ZonaPeligrosa,
    *,
    cambios: dict,
    circulo: tuple[float, float, float] | None = None,
) -> ZonaPeligrosa:
    """cambios: solo campos de CAMPOS_EDITABLES. circulo: (lat, lng, radio_m) si cambia la zona."""
    desconocidos = set(cambios) - CAMPOS_EDITABLES
    if desconocidos:
        raise ValueError(f"Campos no editables: {sorted(desconocidos)}")
    for campo, valor in cambios.items():
        setattr(zona, campo, valor)
    if circulo is not None:
        lat, lng, radio_m = circulo
        zona.centro = punto_desde_latlng(lat, lng)
        zona.radio_m = radio_m
        zona.area = circulo_a_poligono(lat, lng, radio_m)
    db.flush()
    db.refresh(zona)
    return zona
