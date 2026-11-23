import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memoria.settings")

# Redis opcional: sin REDIS_URL las tasks corren en línea (CELERY_TASK_ALWAYS_EAGER
# en settings) y las periódicas las dispara `manage.py tick` (ver
# core/management/commands/tick.py). El beat_schedule de abajo solo se usa
# si se corre Celery beat con Redis.
broker_url = os.getenv("REDIS_URL") or "memory://"
result_backend = os.getenv("REDIS_URL") or "cache+memory://"

app = Celery(
    "memoria",
    broker_url=broker_url,
    result_backend=result_backend,
    result_persistent=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Periodic task schedule
app.conf.beat_schedule = {
    "send-daily-staff-summary": {
        "task": "core.tasks.send_daily_staff_summary",
        "schedule": crontab(
            hour=int(os.getenv("DAILY_SUMMARY_HOUR", "9")),
            minute=int(os.getenv("DAILY_SUMMARY_MINUTE", "0")),
        ),  # Run once per day at 9 AM by default
    },
    "archivo-ciclo-ingesta": {
        "task": "archivo.tasks.ciclo_ingesta",
        "schedule": crontab(minute="*/30"),
    },
    "archivo-procesar-historias": {
        "task": "archivo.tasks.procesar_historias",
        "schedule": crontab(minute="*/15"),
    },
    "archivo-recrawls": {
        "task": "archivo.tasks.recrawls_pendientes",
        "schedule": crontab(minute=40),
    },
    "juego-burbujas": {
        "task": "juego.tasks.calcular_burbujas_diario",
        "schedule": crontab(hour=2, minute=15),
    },
    "juego-armar-jornada": {
        "task": "juego.tasks.armar_jornada_del_dia",
        "schedule": crontab(hour=5, minute=30),
    },
    "archivo-cerrar-historias": {
        "task": "archivo.tasks.cerrar_historias",
        "schedule": crontab(minute=5),
    },
}
