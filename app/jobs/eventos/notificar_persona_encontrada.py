"""Push a quien reportó una persona desaparecida cuando la marcan como encontrada (B3)."""

from uuid import UUID

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.enums import EstadoCasoPersona
from app.models.persona_desaparecida import PersonaDesaparecida
from app.services import notificaciones_service


@celery_app.task
def notificar_persona_encontrada(persona_id: str) -> dict:
    db = SessionLocal()
    try:
        persona = db.get(PersonaDesaparecida, UUID(persona_id))
        if persona is None or persona.estado_caso != EstadoCasoPersona.ENCONTRADO:
            return {"status": "no_aplica", "persona_id": persona_id}
        dispositivos = notificaciones_service.notificar_usuarios(
            db,
            [persona.reportado_por],
            titulo="Persona encontrada",
            cuerpo=f"La ficha de {persona.nombre} se marcó como encontrada.",
            datos={"tipo": "persona", "persona_id": persona_id},
        )
        return {"status": "ok", "persona_id": persona_id, "dispositivos": dispositivos}
    finally:
        db.close()
