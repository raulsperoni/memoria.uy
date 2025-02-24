from celery import shared_task
from celery.utils.log import get_task_logger
from core.parse import parse_noticia
from core.models import Noticia, Entidad, NoticiaEntidad

logger = get_task_logger(__name__)


@shared_task
def parse(noticia_id, html):
    noticia = Noticia.objects.get(id=noticia_id)
    logger.info(f"Parsing ***REMOVED***noticia.enlace***REMOVED***")
    articulo = parse_noticia(html)
    noticia.fuente = articulo.fuente
    noticia.categoria = articulo.categoria
    noticia.resumen = articulo.resumen
    noticia.save()
    logger.info(f"Parsed ***REMOVED***noticia.enlace***REMOVED***")
    for entidad_nombrada in articulo.entidades:
        logger.info(f"Found entity ***REMOVED***entidad_nombrada***REMOVED***")
        entidad, _ = Entidad.objects.get_or_create(
            nombre=entidad_nombrada.nombre, tipo=entidad_nombrada.tipo
        )
        NoticiaEntidad.objects.create(
            noticia=noticia, entidad=entidad, sentimiento=entidad_nombrada.sentimiento
        )
    logger.info(f"Entities saved for ***REMOVED***noticia.enlace***REMOVED***")
    return noticia_id
