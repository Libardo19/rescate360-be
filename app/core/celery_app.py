from celery import Celery

from app.core.config import get_settings
from app.jobs.beat_schedule import BEAT_SCHEDULE

settings = get_settings()

celery_app = Celery("rescate360", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    timezone="America/Bogota",
    enable_utc=True,
    # Los jobs deben ser idempotentes: se confirman al terminar y se reintentan si el worker muere.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule=BEAT_SCHEDULE,
)
celery_app.autodiscover_tasks(["app.jobs.eventos", "app.jobs.programados"])
