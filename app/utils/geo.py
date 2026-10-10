"""Utilidades geoespaciales — PostGIS a través de GeoAlchemy2.

Los modelos usan columnas `Geometry(..., srid=4326)`, que miden distancias en
GRADOS, no en metros (problema #6 del diagnóstico). Toda consulta de
"cerca de" debe castear a `::geography` para que la distancia se interprete
en metros reales. Esa regla vive SOLO aquí, nadie más debe escribir
ST_DWithin/ST_Buffer a mano en otro archivo.
"""

from __future__ import annotations

from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_Buffer, ST_DWithin
from geoalchemy2.types import Geography, Geometry
from sqlalchemy import cast
from sqlalchemy.sql.elements import ColumnElement

SRID = 4326


def punto_desde_latlng(lat: float, lng: float) -> WKTElement:
    """Crea un punto PostGIS a partir de coordenadas sueltas.

    OJO con el orden: PostGIS espera (longitud, latitud), invertido
    respecto al {"lat":, "lng":} que usa el contrato de la API.
    """
    return WKTElement(f"POINT({lng} {lat})", srid=SRID)


def latlng_desde_punto(geom) -> dict | None:
    """Convierte una geometría punto (cargada por GeoAlchemy2) de vuelta
    a {"lat":, "lng":} para la respuesta JSON de la API."""
    if geom is None:
        return None
    from shapely import wkb

    punto = wkb.loads(bytes(geom.data))
    return {"lat": punto.y, "lng": punto.x}


def circulo_a_poligono(lat: float, lng: float, radio_m: float):
    """Polígono aproximadamente circular de radio_m metros alrededor de
    (lat, lng), para guardar en columnas Geometry(POLYGON) (ej. zonas
    peligrosas dibujadas como círculo en el contrato de la API).

    Se castea a geography para que ST_Buffer calcule el radio en METROS
    (en geometry pura, el radio se interpretaría en grados).
    """
    punto = punto_desde_latlng(lat, lng)
    return cast(
        ST_Buffer(cast(punto, Geography), radio_m),
        Geometry(geometry_type="POLYGON", srid=SRID),
    )


def cerca_de(columna: ColumnElement, lat: float, lng: float, metros: float):
    """Condición SQL: `columna` (Geometry POINT o POLYGON) está a `metros`
    o menos de (lat, lng). Úsala dentro de un `.where(...)` de SQLAlchemy:

        query.where(cerca_de(CentroAyuda.ubicacion, lat, lng, 5000))

    Ambos lados se castean a geography, así el tercer argumento de
    ST_DWithin se interpreta en metros reales, no en grados.
    """
    punto = punto_desde_latlng(lat, lng)
    return ST_DWithin(
        cast(columna, Geography),
        cast(punto, Geography),
        metros,
    )