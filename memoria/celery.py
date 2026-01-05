import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memoria.settings")

# Use Redis as broker and result backend
broker_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
result_backend = os.getenv('REDIS_URL', 'redis://redis:6379/0')

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
    'update-voter-clusters-daily': {
        'task': 'core.tasks.update_voter_clusters',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM every day
        'kwargs': {
            'time_window_days': 30,
            'min_voters': 50,
            'min_votes_per_voter': 3,
        },
    },
}
