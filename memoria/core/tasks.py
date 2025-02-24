from celery import shared_task
from celery.utils.log import get_task_logger
from core.parse import parse_noticia
from core.models import Noticia, Entidad, NoticiaEntidad

logger = get_task_logger(__name__)


@shared_task
def parse(noticia_id, html):
    noticia = Noticia.objects.get(id=noticia_id)
    logger.info(f"Parsing {noticia.enlace}")
    articulo = parse_noticia(html)
    if not articulo:
        logger.error(f"Failed to parse {noticia.enlace}")
        return
    noticia.fuente = articulo.fuente
    noticia.categoria = articulo.categoria if articulo.categoria else "otros"
    noticia.resumen = articulo.resumen
    noticia.save()
    logger.info(f"Parsed {noticia.enlace}")
    for entidad_nombrada in articulo.entidades:
        logger.info(f"Found entity {entidad_nombrada}")
        entidad, _ = Entidad.objects.get_or_create(
            nombre=entidad_nombrada.nombre, tipo=entidad_nombrada.tipo
        )
        NoticiaEntidad.objects.get_or_create(
            noticia=noticia,
            entidad=entidad,
            defaults={"sentimiento": entidad_nombrada.sentimiento},
        )
    logger.info(f"Entities saved for  {noticia.enlace}")
    return noticia_id
