import os
from celery import Celery

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
