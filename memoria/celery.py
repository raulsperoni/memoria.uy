import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memoria.settings")

# Default to filesystem broker for local development
use_redis = os.getenv('USE_REDIS_BROKER', 'False').lower() == 'true'

if use_redis:
    # Use Redis as broker when specified
    broker_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    result_backend = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    broker_transport_options = None
else:
    # Use filesystem as broker by default
    broker_url = "filesystem://"
    result_backend = None
    broker_transport_options = {
        "data_folder_in": "./.data/broker",
        "data_folder_out": "./.data/broker/",
        "data_folder_processed": "./.data/broker/processed",
    }

app = Celery(
    "memoria",
    broker_url=broker_url,
    result_backend=result_backend,
    broker_transport_options=broker_transport_options,
    result_persistent=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Ensure broker directories exist when using filesystem
if not use_redis:
    for f in ["./.data/broker", "./.data/broker/out", "./.data/broker/processed"]:
        if not os.path.exists(f):
            os.makedirs(f, exist_ok=True)
