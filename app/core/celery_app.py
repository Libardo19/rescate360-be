from celery import Celery

from app.core.config import get_settings
from app.jobs.beat_schedule import BEAT_SCHEDULE

settings = get_settings()

# Módulos con tareas. autodiscover_tasks() solo busca archivos llamados tasks.py,
# así que cada job nuevo se registra aquí (archivo compartido: solo agregar líneas).
JOBS = [
    "app.jobs.eventos.clasificar_prioridad_ia",
    "app.jobs.eventos.clasificar_reporte_ia",
    "app.jobs.eventos.enviar_sms_respaldo",
    "app.jobs.eventos.notificar_alerta_general",
    "app.jobs.eventos.notificar_alerta_zona",
    "app.jobs.eventos.notificar_persona_encontrada",
    "app.jobs.eventos.notificar_voluntarios_cercanos",
    "app.jobs.eventos.procesar_lote_offline",
    "app.jobs.programados.expirar_alertas",
    "app.jobs.programados.limpiar_datos_retencion",
    "app.jobs.programados.marcar_reportes_no_verificables",
    "app.jobs.programados.recalcular_estadisticas",
    "app.jobs.programados.sincronizar_sismos",
    "app.jobs.programados.vencer_check_ins",
]

celery_app = Celery("rescate360", broker=settings.redis_url, backend=settings.redis_url, include=JOBS)
celery_app.conf.update(
    timezone="America/Bogota",
    enable_utc=True,
    # Los jobs deben ser idempotentes: se confirman al terminar y se reintentan si el worker muere.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule=BEAT_SCHEDULE,
)
