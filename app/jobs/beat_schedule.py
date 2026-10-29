# Jobs programados de Celery Beat (app/jobs/programados/). El nombre de la tarea es
# "<módulo>.<función>", como lo registra @celery_app.task.
from celery.schedules import crontab

BEAT_SCHEDULE: dict = {
    "expirar-alertas": {
        "task": "app.jobs.programados.expirar_alertas.expirar_alertas",
        "schedule": crontab(minute="*/5"),
    },
}
