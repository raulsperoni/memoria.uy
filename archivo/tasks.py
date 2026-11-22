"""Tasks de Celery del archivo. Ver archivo/pipeline.py."""

import logging
import os

from celery import shared_task
from django.utils import timezone

from core.tasks import task_lock

from . import pipeline
from .models import Fuente, Historia, Medio

logger = logging.getLogger(__name__)


def ingesta_activa():
    return os.environ.get("INGESTA_ACTIVA", "True") == "True"


@shared_task
@task_lock(timeout=60 * 20)
def ciclo_ingesta():
    """Ciclo completo: descubrir → filtrar → extraer → agrupar. Cada 30 min."""
    if not ingesta_activa():
        return "ingesta desactivada"
    nuevas = 0
    for medio in Medio.objects.filter(activo=True):
        try:
            nuevas += len(pipeline.descubrir(medio))
        except Exception:
            logger.exception("Descubrimiento falló para %s", medio)

    for f in Fuente.objects.filter(estado="descubierta", interes__isnull=True).select_related("medio")[:500]:
        try:
            pipeline.filtrar(f)
        except Exception:
            logger.exception("Filtro falló para %s", f.url)

    extraidas = 0
    pendientes = (
        Fuente.objects.filter(estado="descubierta", interes__isnull=False)
        .order_by("-interes", "-publicada_en")
    )
    for f in pendientes[:100]:
        if not pipeline.extraer(f):
            if pipeline.extracciones_hoy() >= pipeline.MAX_EXTRACCIONES_DIA():
                break
            continue
        extraidas += 1
        try:
            pipeline.agrupar(f)
        except Exception:
            logger.exception("Agrupar falló para %s", f.url)
    return f"nuevas={nuevas} extraidas={extraidas}"


@shared_task
@task_lock(timeout=60 * 30)
def procesar_historias():
    """Procesa historias quietas con fuentes nuevas. Cada 15 min."""
    if not ingesta_activa():
        return "ingesta desactivada"
    try:
        pipeline.fusionar_duplicadas()
    except Exception:
        logger.exception("Fusión de historias falló")
    n = 0
    for h in list(pipeline.historias_listas()):
        try:
            if pipeline.procesar_historia(h):
                n += 1
        except Exception:
            logger.exception("Procesar historia %s falló", h.pk)
    pipeline.programar_recrawls()
    return f"procesadas={n}"


@shared_task
@task_lock(timeout=60 * 20)
def recrawls_pendientes():
    """Re-captura fuentes programadas para detectar cambios. Cada hora."""
    if not ingesta_activa():
        return "ingesta desactivada"
    n = 0
    for f in Fuente.objects.filter(proximo_recrawl__lte=timezone.now())[:100]:
        try:
            if pipeline.recrawl(f):
                n += 1
        except Exception:
            logger.exception("Recrawl falló para %s", f.url)
    return f"cambios={n}"


@shared_task
def cerrar_historias():
    return pipeline.cerrar_historias()
