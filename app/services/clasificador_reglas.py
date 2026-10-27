"""Clasificador de respaldo por reglas: se usa cuando Gemini no está disponible
(sin GEMINI_API_KEY, sin internet, saturado o con una respuesta inválida).

Así el sistema SIEMPRE sugiere una prioridad y una organización, aunque con confianza baja,
y el administrador la puede corregir. Las reglas son deliberadamente simples y explicables.
"""

import unicodedata
from uuid import UUID

from app.models.enums import PrioridadSolicitud
from app.schemas.ia_schema import CasoIA, ClasificacionIA, OrganizacionIA

CONFIANZA_REGLAS = 0.4

_ORDEN = [PrioridadSolicitud.BAJA, PrioridadSolicitud.MEDIA, PrioridadSolicitud.ALTA, PrioridadSolicitud.CRITICA]

# Prioridad de partida según el tipo del caso
_PRIORIDAD_BASE: dict[str, PrioridadSolicitud] = {
    # solicitudes de ayuda
    "rescate": PrioridadSolicitud.ALTA,
    "medica": PrioridadSolicitud.ALTA,
    "refugio": PrioridadSolicitud.MEDIA,
    "alimentaria": PrioridadSolicitud.MEDIA,
    "ropa": PrioridadSolicitud.BAJA,
    # reportes de incidentes
    "incendio": PrioridadSolicitud.ALTA,
    "inundacion": PrioridadSolicitud.ALTA,
    "deslizamiento": PrioridadSolicitud.ALTA,
    "sismo": PrioridadSolicitud.ALTA,
    "accidente": PrioridadSolicitud.MEDIA,
    "robo": PrioridadSolicitud.MEDIA,
}

# Señales de riesgo para la vida: pasan directo a crítica
_CRITICAS = (
    "atrapad", "inconscient", "no respira", "sangrando", "hemorragia", "infarto", "convulsion",
    "ahogand", "personas adentro", "gente adentro", "sepultad", "explosion", "disparo",
)
# Agravantes: suben un nivel
_AGRAVANTES = (
    "herid", "nino", "bebe", "menor", "adulto mayor", "anciano", "embarazada", "discapacidad",
    "fuego", "humo", "gas", "derrumbe", "arma", "varias personas", "familia",
)
# Atenuantes: bajan un nivel
_ATENUANTES = ("controlad", "sin heridos", "no hay personas", "no hay heridos", "leve", "ya paso")

# Organizaciones preferidas según el tipo del caso (en orden)
_ORGANIZACION_POR_TIPO: dict[str, tuple[str, ...]] = {
    "incendio": ("bomberos", "defensa_civil"),
    "rescate": ("bomberos", "defensa_civil", "cruz_roja"),
    "deslizamiento": ("defensa_civil", "bomberos"),
    "sismo": ("defensa_civil", "bomberos", "cruz_roja"),
    "inundacion": ("defensa_civil", "bomberos"),
    "medica": ("cruz_roja", "defensa_civil", "bomberos"),
    "accidente": ("cruz_roja", "bomberos", "policia"),
    "robo": ("policia",),
    "refugio": ("ong", "cruz_roja", "defensa_civil"),
    "alimentaria": ("ong", "cruz_roja", "defensa_civil"),
    "ropa": ("ong", "cruz_roja"),
}
# Para tipos escritos por el ciudadano ("fuga de gas", "pelea"…): palabra → organizaciones
_ORGANIZACION_POR_PALABRA: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("gas", "fuego", "humo", "explosion", "arbol", "cable"), ("bomberos", "defensa_civil")),
    (("pelea", "asalto", "disparo", "arma", "violencia", "hurto"), ("policia",)),
    (("herid", "enferm", "desmay"), ("cruz_roja", "bomberos")),
)
_POR_DEFECTO = ("defensa_civil", "ong", "cruz_roja")


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.lower().split())


def _mover(prioridad: PrioridadSolicitud, pasos: int) -> PrioridadSolicitud:
    i = min(max(_ORDEN.index(prioridad) + pasos, 0), len(_ORDEN) - 1)
    return _ORDEN[i]


def _elegir_organizacion(caso: CasoIA, organizaciones: list[OrganizacionIA]) -> OrganizacionIA | None:
    tipo = _normalizar(caso.tipo)
    preferidas = _ORGANIZACION_POR_TIPO.get(tipo)
    if preferidas is None:
        texto = f"{tipo} {_normalizar(caso.descripcion)}"
        preferidas = next(
            (orgs for palabras, orgs in _ORGANIZACION_POR_PALABRA if any(p in texto for p in palabras)),
            _POR_DEFECTO,
        )
    for tipo_org in preferidas:
        for org in organizaciones:
            if org.tipo == tipo_org:
                return org
    return None


def clasificar(caso: CasoIA, organizaciones: list[OrganizacionIA]) -> ClasificacionIA:
    texto = _normalizar(f"{caso.tipo} {caso.descripcion}")
    prioridad = _PRIORIDAD_BASE.get(_normalizar(caso.tipo), PrioridadSolicitud.MEDIA)
    motivos = [f"tipo «{caso.tipo}» → {prioridad.value}"]

    criticas = [p for p in _CRITICAS if p in texto]
    if criticas:
        prioridad = PrioridadSolicitud.CRITICA
        motivos.append(f"riesgo para la vida ({', '.join(criticas[:2])}) → crítica")
    else:
        agravantes = [p for p in _AGRAVANTES if p in texto]
        if agravantes:
            prioridad = _mover(prioridad, 1)
            motivos.append(f"agravante ({', '.join(agravantes[:2])}) → {prioridad.value}")
        atenuantes = [p for p in _ATENUANTES if p in texto]
        if atenuantes:
            prioridad = _mover(prioridad, -1)
            motivos.append(f"atenuante ({atenuantes[0]}) → {prioridad.value}")

    organizacion = _elegir_organizacion(caso, organizaciones)
    motivos.append(f"organización: {organizacion.nombre if organizacion else 'ninguna adecuada activa'}")
    return ClasificacionIA(
        prioridad=prioridad,
        confianza=CONFIANZA_REGLAS,
        razonamiento=("Clasificado por reglas (IA no disponible): " + "; ".join(motivos) + ".")[:500],
        organizacion_id=UUID(str(organizacion.id)) if organizacion else None,
        fuente="reglas",
    )
