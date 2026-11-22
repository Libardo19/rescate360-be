"""Feed público de sismos del USGS (GeoJSON, se actualiza cada minuto).

Se quedan los sismos de todo el mundo (el mapa los muestra todos); `en_colombia` decide cuáles
alertan. Si el feed no responde, se deja un log y se devuelve una lista vacía: el job lo vuelve a
intentar al minuto siguiente.
Sin dependencias nuevas: urllib de la librería estándar.
"""

import json
import logging
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import get_settings

logger = logging.getLogger(__name__)

TIMEOUT_S = 10
# Recuadro de Colombia (incluye el mar cercano, de donde vienen muchos sismos sentidos)
LAT_MIN, LAT_MAX = -4.3, 13.5
LNG_MIN, LNG_MAX = -79.1, -66.8


@dataclass(frozen=True)
class SismoFeed:
    id_externo: str
    magnitud: float
    profundidad_km: float | None
    lugar: str
    lat: float
    lng: float
    ocurrido_en: datetime


def en_colombia(lat: float, lng: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX


def parsear(geojson: dict) -> list[SismoFeed]:
    """Convierte el GeoJSON del USGS; ignora los que vienen sin magnitud o con magnitud negativa
    (microsismos que el USGS reporta por debajo de 0 y que nadie siente)."""
    sismos = []
    for feature in geojson.get("features", []):
        propiedades = feature.get("properties") or {}
        coordenadas = (feature.get("geometry") or {}).get("coordinates") or []
        if propiedades.get("mag") is None or float(propiedades["mag"]) < 0 or len(coordenadas) < 2:
            continue
        lng, lat = float(coordenadas[0]), float(coordenadas[1])
        sismos.append(
            SismoFeed(
                id_externo=f"usgs:{feature['id']}",
                magnitud=min(10.0, round(float(propiedades["mag"]), 1)),
                profundidad_km=float(coordenadas[2]) if len(coordenadas) > 2 and coordenadas[2] is not None else None,
                lugar=(propiedades.get("place") or "Sin ubicación")[:200],
                lat=lat,
                lng=lng,
                ocurrido_en=datetime.fromtimestamp(propiedades["time"] / 1000, tz=UTC),
            )
        )
    return sismos


def obtener_recientes(url: str | None = None) -> list[SismoFeed]:
    """Sin `url`: el feed de la última hora."""
    try:
        with urllib.request.urlopen(url or get_settings().sismos_feed_url, timeout=TIMEOUT_S) as respuesta:
            return parsear(json.load(respuesta))
    except Exception:
        logger.exception("No se pudo leer el feed de sismos")
        return []
