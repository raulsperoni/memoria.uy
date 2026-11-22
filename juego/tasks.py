import logging
import os

from celery import shared_task

from core.tasks import task_lock

from .logica import armar_jornada

logger = logging.getLogger(__name__)


@shared_task
@task_lock(timeout=60 * 10)
def armar_jornada_del_dia():
    if os.environ.get("JUEGO_ACTIVO", "True") != "True":
        return "juego desactivado"
    j = armar_jornada()
    return f"jornada {j.fecha} con {j.items.count()} items" if j else "sin candidatas suficientes"
