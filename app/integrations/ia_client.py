"""Cliente de Gemini: analiza un caso (solicitud de ayuda o reporte de incidente) y sugiere
prioridad y organización. Solo SUGIERE: el administrador puede cambiar las dos cosas.

Prueba los modelos en orden (GEMINI_MODEL y luego GEMINI_MODELOS_RESPALDO): Google satura o
retira modelos con frecuencia. Si ninguno responde, lanza IAClasificacionError y quien llama
usa el clasificador por reglas.
"""

import json
import logging
from uuid import UUID

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.models.enums import PrioridadSolicitud
from app.schemas.ia_schema import CasoIA, ClasificacionIA, OrganizacionIA

logger = logging.getLogger(__name__)

# Errores de Gemini por los que vale la pena probar el siguiente modelo
_REINTENTABLES = {404, 429, 500, 502, 503, 504}


class IAPrioridadRespuesta(BaseModel):
    """Lo que debe devolver Gemini (JSON)."""

    prioridad: PrioridadSolicitud
    confianza: float = Field(ge=0.0, le=1.0)
    razonamiento: str = Field(min_length=10, max_length=500)
    organizacion_id: str | None = None
    organizacion_sugerida: str | None = None


class IAClasificacionError(Exception):
    pass


_QUE_ES = {
    "solicitud": "una SOLICITUD DE AYUDA (una persona pide ayuda para sí misma o su familia)",
    "reporte": "un REPORTE DE INCIDENTE (un ciudadano avisa de algo que está pasando en su comunidad)",
}


def construir_prompt(caso: CasoIA, organizaciones: list[OrganizacionIA]) -> str:
    orgs = "\n".join(f"- id: {o.id} | nombre: {o.nombre} | tipo: {o.tipo}" for o in organizaciones)
    evidencias = f"\n- evidencias adjuntas: {caso.evidencias} (fotos o videos)" if caso.clase == "reporte" else ""
    return f"""Eres el sistema de apoyo a la coordinación de emergencias de RESCATE360 (Colombia).
Vas a analizar {_QUE_ES[caso.clase]} y a SUGERIR dos cosas: su prioridad y la organización
que debe atenderlo. No decides solo: un administrador revisa y puede cambiar ambas.

CASO:
- tipo: {caso.tipo}
- origen: {caso.origen}
- dirección: {caso.direccion or 'sin dirección'}
- descripción: {caso.descripcion}{evidencias}

ORGANIZACIONES ACTIVAS (elige SOLO entre estas, por su id):
{orgs or '(no hay organizaciones activas)'}

CRITERIOS DE PRIORIDAD:
- critica: riesgo inmediato para la vida (personas atrapadas, inconscientes, sin respirar, incendio con gente adentro, hemorragia).
- alta: personas heridas o en peligro, menores, adultos mayores, embarazadas, emergencias que crecen rápido (incendio, inundación, deslizamiento, sismo).
- media: necesidad real sin riesgo inmediato para la vida (refugio, alimentos, accidente sin heridos graves, robo).
- baja: necesidades que pueden esperar (ropa, daños menores, situaciones ya controladas).

CRITERIOS DE ORGANIZACIÓN (según su tipo): bomberos → incendios, rescates, fugas de gas, estructuras;
cruz_roja → atención médica, heridos, apoyo humanitario; defensa_civil → inundaciones, deslizamientos,
sismos, evacuación; policia → robos, violencia, orden público; ong → alimentos, ropa, refugio.
Si ninguna organización de la lista es adecuada, organizacion_id = null.

Responde ÚNICAMENTE con este JSON (sin texto extra):
{{
  "prioridad": "baja|media|alta|critica",
  "confianza": 0.0-1.0,
  "razonamiento": "explicación breve en español (10 a 400 caracteres)",
  "organizacion_id": "id exacto de la lista o null",
  "organizacion_sugerida": "nombre de esa organización o null"
}}
"""


def _llamar(modelo: str, prompt: str) -> IAPrioridadRespuesta:
    settings = get_settings()
    url = f"{settings.gemini_base_url}/models/{modelo}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
        },
    }
    with httpx.Client(timeout=settings.gemini_timeout) as cliente:
        # La clave no debe terminar en las URLs que httpx escribe en los logs.
        respuesta = cliente.post(url, headers={"x-goog-api-key": settings.gemini_api_key}, json=payload)
        respuesta.raise_for_status()
        datos = respuesta.json()
    try:
        texto = datos["candidates"][0]["content"]["parts"][0]["text"]
        return IAPrioridadRespuesta.model_validate(json.loads(texto))
    except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
        raise IAClasificacionError(f"Respuesta inválida de {modelo}: {exc}") from exc


def _organizacion(respuesta: IAPrioridadRespuesta, organizaciones: list[OrganizacionIA]) -> UUID | None:
    """La organización elegida debe estar en la lista: por id y, si no, por nombre exacto."""
    por_id = {str(o.id): o.id for o in organizaciones}
    if respuesta.organizacion_id and respuesta.organizacion_id in por_id:
        return por_id[respuesta.organizacion_id]
    if respuesta.organizacion_sugerida:
        nombre = " ".join(respuesta.organizacion_sugerida.lower().split())
        for o in organizaciones:
            if " ".join(o.nombre.lower().split()) == nombre:
                return o.id
    return None


def clasificar(caso: CasoIA, organizaciones: list[OrganizacionIA]) -> ClasificacionIA:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise IAClasificacionError("GEMINI_API_KEY no configurada")

    prompt = construir_prompt(caso, organizaciones)
    errores: list[str] = []
    for modelo in [settings.gemini_model, *settings.gemini_modelos_respaldo]:
        try:
            respuesta = _llamar(modelo, prompt)
        except httpx.HTTPStatusError as exc:
            errores.append(f"{modelo}: HTTP {exc.response.status_code}")
            if exc.response.status_code in _REINTENTABLES:
                continue
            break  # clave inválida u otro error que otro modelo no arregla
        except (httpx.HTTPError, IAClasificacionError) as exc:
            errores.append(f"{modelo}: {exc}")
            continue
        return ClasificacionIA(
            prioridad=respuesta.prioridad,
            confianza=respuesta.confianza,
            razonamiento=respuesta.razonamiento,
            organizacion_id=_organizacion(respuesta, organizaciones),
            fuente=f"gemini:{modelo}",
        )
    logger.warning("Gemini no clasificó el caso: %s", "; ".join(errores))
    raise IAClasificacionError("; ".join(errores))
