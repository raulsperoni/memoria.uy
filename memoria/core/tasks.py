from celery import shared_task
from celery.utils.log import get_task_logger
from core.models import Noticia, Entidad, NoticiaEntidad
from core import parse

logger = get_task_logger(__name__)


@shared_task
def enrich_markdown(noticia_id, html):
    noticia = Noticia.objects.get(id=noticia_id)
    if noticia.archivo_url:
        logger.info(f"Fetching archived URL for {noticia.enlace}")
        markdown = parse.parse_noticia_markdown(html, noticia.titulo)
        if markdown:
            noticia.markdown = markdown
            noticia.save()
            logger.info(f"Enriched {noticia.enlace} with markdown")
            enrich_content.delay(noticia_id)
            return noticia_id
        logger.error(f"Failed to enrich {noticia.enlace} with markdown")
    else:
        logger.error(f"No archived URL for {noticia.enlace}")
    return noticia_id


@shared_task
def enrich_content(noticia_id):
    noticia = Noticia.objects.get(id=noticia_id)
    if noticia.markdown:
        articulo = parse.parse_noticia(noticia.markdown)
        if articulo:
            noticia.titulo = articulo.titulo
            noticia.fuente = articulo.fuente
            noticia.categoria = articulo.categoria if articulo.categoria else "otros"
            noticia.resumen = articulo.resumen
            noticia.save()
            logger.info(f"Enriched {noticia.enlace} with content")
            if articulo.entidades:
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
                logger.info(f"Entities saved for {noticia.enlace}")
            return noticia_id
        logger.error(f"Failed to enrich {noticia.enlace} with content")
    else:
        logger.error(f"No markdown content for {noticia.enlace}")
    return noticia_id
