# Jobs programados de Celery Beat (app/jobs/programados/). El nombre de la tarea es
# "<módulo>.<función>", como lo registra @celery_app.task.
from celery.schedules import crontab

BEAT_SCHEDULE: dict = {
    "expirar-alertas": {
        "task": "app.jobs.programados.expirar_alertas.expirar_alertas",
        "schedule": crontab(minute="*/5"),
    },
    "sincronizar-sismos": {
        "task": "app.jobs.programados.sincronizar_sismos.sincronizar_sismos",
        "schedule": 60.0,
    },
    "vencer-check-ins": {
        "task": "app.jobs.programados.vencer_check_ins.vencer_check_ins",
        "schedule": 60.0,
    },
}
