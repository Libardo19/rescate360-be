import json
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.models.enums import PrioridadSolicitud


class IAPrioridadRespuesta(BaseModel):
    prioridad: PrioridadSolicitud
    confianza: float = Field(ge=0.0, le=1.0)
    razonamiento: str = Field(min_length=10, max_length=500)
    organizacion_sugerida: str | None = None


class IAClasificacionError(Exception):
    pass


def _construir_prompt(
    tipo: str,
    descripcion: str,
    direccion: str | None,
    origen: str,
    organizaciones_activas: list[dict[str, Any]],
) -> str:
    orgs_texto = []
    for org in organizaciones_activas:
        orgs_texto.append(
            f"- id:{org.get('id')} | nombre:{org.get('nombre')} | tipo:{org.get('tipo')}"
        )

    orgs_bloque = "\n".join(orgs_texto) if orgs_texto else "(No hay organizaciones activas registradas)"

    prompt = f"""Eres un sistema de apoyo para coordinación de emergencias de RESCATE360.
Tu ÚNICA tarea es clasificar la prioridad de una solicitud de ayuda y sugerir la organización más oportuna.

NO DECIDES SOLO. Solo sugieres. Un administrador puede cambiar la prioridad manualmente.

DATOS DE LA SOLICITUD:
- tipo: {tipo}
- origen: {origen}
- direccion: {direccion or 'Sin dirección'}
- descripcion: {descripcion}

ORGANIZACIONES ACTIVAS DISPONIBLES (elige ÚNICAMENTE entre estas):
{orgs_bloque}

INSTRUCCIONES:
1. Asigna prioridad válida: baja, media, alta o critica. NUNCA 'pendiente'.
2. Elige la organización MÁS OPORTUNA o EXACTA entre las listadas según el tipo de solicitud.
3. Si NINGUNA organización de la lista es adecuada para este caso, responde organizacion_sugerida = null.
4. Sé conciso y objetivo en el razonamiento.
5. Responde ÚNICAMENTE con JSON válido, sin texto extra.

FORMATO DE RESPUESTA OBLIGATORIO:
{{
    "prioridad": "baja|media|alta|critica",
    "confianza": 0.0-1.0,
    "razonamiento": "explicación breve (10-500 caracteres)",
    "organizacion_sugerida": "nombre exacto de la organización elegida o null"
}}
"""
    return prompt


def clasificar_solicitud(
    *,
    tipo: str,
    descripcion: str,
    direccion: str | None,
    origen: str,
    organizaciones_activas: list[dict[str, Any]],
) -> IAPrioridadRespuesta:
    settings = get_settings()

    if not settings.gemini_api_key:
        raise IAClasificacionError("GEMINI_API_KEY no configurada")

    prompt = _construir_prompt(tipo, descripcion, direccion, origen, organizaciones_activas)

    url = f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json",
        },
    }

    headers = {"Content-Type": "application/json"}
    params = {"key": settings.gemini_api_key}

    try:
        with httpx.Client(timeout=settings.gemini_timeout) as client:
            resp = client.post(url, headers=headers, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException as exc:
        raise IAClasificacionError("Timeout al llamar a Gemini") from exc
    except httpx.HTTPStatusError as exc:
        raise IAClasificacionError(f"Error HTTP de Gemini: {exc.response.status_code}") from exc
    except Exception as exc:
        raise IAClasificacionError(f"Error al llamar a Gemini: {exc}") from exc

    try:
        candidatos = data.get("candidates") or []
        if not candidatos:
            raise IAClasificacionError("Respuesta de Gemini sin candidatos")
        contenido = candidatos[0].get("content") or {}
        partes = contenido.get("parts") or []
        if not partes:
            raise IAClasificacionError("Respuesta de Gemini sin partes")
        texto = partes[0].get("text") or ""
        if not texto:
            raise IAClasificacionError("Respuesta de Gemini vacía")
        parsed_json = json.loads(texto)
    except IAClasificacionError:
        raise
    except Exception as exc:
        raise IAClasificacionError(f"Error al parsear respuesta JSON de Gemini: {exc}") from exc

    try:
        return IAPrioridadRespuesta.model_validate(parsed_json)
    except ValidationError as exc:
        raise IAClasificacionError(f"Respuesta de Gemini inválida según schema: {exc}") from exc
