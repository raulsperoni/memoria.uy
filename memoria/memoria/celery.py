import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memoria.settings")
app = Celery(
    "memoria",
    broker_url="filesystem://",
    broker_transport_options={
        "data_folder_in": "./.data/broker",
        "data_folder_out": "./.data/broker/",
        "data_folder_processed": "./.data/broker/processed",
    },
    result_persistent=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

for f in ["./broker/out", "./broker/processed"]:
    if not os.path.exists(f):
        os.makedirs(f)
